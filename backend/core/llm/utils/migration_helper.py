"""
Model Migration Helper

This module helps identify and migrate deprecated models to their replacements.
"""

import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from ..registry import get_model_registry
from ..manager import get_llm_manager

logger = logging.getLogger(__name__)


class ModelMigrationHelper:
    """Helper class for model migration and deprecation handling"""
    
    def __init__(self):
        self.registry = get_model_registry()
        self.manager = get_llm_manager()
    
    def check_deprecated_models(self) -> List[Dict[str, Any]]:
        """Check for deprecated models in current configuration"""
        deprecated_models = []
        
        # Check environment variables
        env_vars_to_check = [
            "TICKET_VIEW_MODEL_NAME",
            "TICKET_SIMILAR_MODEL_NAME",
            "SUMMARIZATION_MODEL_NAME",
            "REALTIME_MODEL_NAME",
            "BATCH_MODEL_NAME",
            "QA_MODEL_NAME",
            "CHAT_MODEL_NAME",
            "ANALYSIS_MODEL_NAME"
        ]
        
        for env_var in env_vars_to_check:
            model_name = os.getenv(env_var)
            if model_name:
                provider_var = env_var.replace("_NAME", "_PROVIDER")
                provider = os.getenv(provider_var, "openai")
                
                model_spec = self.registry.get_model(provider, model_name)
                if model_spec and model_spec.deprecated:
                    deprecated_models.append({
                        "env_var": env_var,
                        "provider": provider,
                        "model": model_name,
                        "deprecation_date": model_spec.deprecation_date,
                        "replacement": model_spec.replacement,
                        "migration_guide": model_spec.migration_guide
                    })
        
        return deprecated_models
    
    def get_migration_recommendations(self) -> Dict[str, str]:
        """Get migration recommendations for deprecated models"""
        recommendations = {}
        deprecated_models = self.check_deprecated_models()
        
        for dep_model in deprecated_models:
            env_var = dep_model["env_var"]
            replacement = dep_model["replacement"]
            
            if replacement:
                recommendations[env_var] = replacement
            else:
                # Try to find a suitable replacement from registry
                use_case = self._get_use_case_from_env_var(env_var)
                if use_case:
                    models = self.registry.get_models_for_use_case(use_case)
                    for provider, model in models:
                        model_spec = self.registry.get_model(provider, model)
                        if model_spec and not model_spec.deprecated:
                            recommendations[env_var] = model
                            break
        
        return recommendations
    
    def _get_use_case_from_env_var(self, env_var: str) -> Optional[str]:
        """Map environment variable to use case"""
        mapping = {
            "TICKET_VIEW_MODEL_NAME": "summarization",
            "TICKET_SIMILAR_MODEL_NAME": "summarization",
            "SUMMARIZATION_MODEL_NAME": "summarization",
            "REALTIME_MODEL_NAME": "chat",
            "BATCH_MODEL_NAME": "analysis",
            "QA_MODEL_NAME": "question_answering",
            "CHAT_MODEL_NAME": "chat",
            "ANALYSIS_MODEL_NAME": "analysis"
        }
        return mapping.get(env_var)
    
    def generate_migration_script(self) -> str:
        """Generate a shell script to update environment variables"""
        recommendations = self.get_migration_recommendations()
        
        if not recommendations:
            return "# No deprecated models found - configuration is up to date!"
        
        script_lines = [
            "#!/bin/bash",
            "# Model Migration Script",
            f"# Generated on: {datetime.now().isoformat()}",
            "#",
            "# This script updates deprecated model configurations",
            "",
            "# Backup current .env file",
            "cp .env .env.backup.$(date +%Y%m%d_%H%M%S)",
            "",
            "# Update deprecated models"
        ]
        
        for env_var, new_model in recommendations.items():
            script_lines.append(f'echo "Updating {env_var} to {new_model}"')
            script_lines.append(f'sed -i "s/{env_var}=.*/{env_var}={new_model}/g" .env')
            script_lines.append("")
        
        script_lines.extend([
            "echo 'Migration complete!'",
            "echo 'Old configuration backed up to .env.backup.*'",
            "echo 'Please restart your application to use the new models.'"
        ])
        
        return "\n".join(script_lines)
    
    def print_deprecation_report(self) -> None:
        """Print a detailed deprecation report"""
        deprecated_models = self.check_deprecated_models()
        
        if not deprecated_models:
            print("✅ No deprecated models found in current configuration!")
            return
        
        print("⚠️  DEPRECATED MODELS DETECTED")
        print("=" * 60)
        
        for dep_model in deprecated_models:
            print(f"\nEnvironment Variable: {dep_model['env_var']}")
            print(f"Current Model: {dep_model['provider']}:{dep_model['model']}")
            
            if dep_model['deprecation_date']:
                dep_date = datetime.strptime(dep_model['deprecation_date'], "%Y-%m-%d")
                days_until = (dep_date - datetime.now()).days
                if days_until > 0:
                    print(f"Deprecation Date: {dep_model['deprecation_date']} ({days_until} days remaining)")
                else:
                    print(f"Deprecation Date: {dep_model['deprecation_date']} (ALREADY DEPRECATED)")
            
            if dep_model['replacement']:
                print(f"Recommended Replacement: {dep_model['replacement']}")
            
            if dep_model['migration_guide']:
                print(f"Migration Guide: {dep_model['migration_guide']}")
            
            print("-" * 40)
        
        print("\n💡 To generate a migration script, run:")
        print("   python -m core.llm.utils.migration_helper --generate-script")


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Model Migration Helper")
    parser.add_argument("--check", action="store_true", help="Check for deprecated models")
    parser.add_argument("--generate-script", action="store_true", help="Generate migration script")
    parser.add_argument("--output", default="migrate_models.sh", help="Output file for migration script")
    
    args = parser.parse_args()
    
    helper = ModelMigrationHelper()
    
    if args.generate_script:
        script = helper.generate_migration_script()
        with open(args.output, 'w') as f:
            f.write(script)
        os.chmod(args.output, 0o755)  # Make executable
        print(f"✅ Migration script generated: {args.output}")
        print(f"   Run: ./{args.output}")
    else:
        # Default: show deprecation report
        helper.print_deprecation_report()


if __name__ == "__main__":
    main()