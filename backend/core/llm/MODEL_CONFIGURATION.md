# LLM Model Configuration Guide

## Overview

The LLM system uses a flexible, registry-based configuration that allows easy model switching through environment variables and automatic deprecation handling.

## Configuration Hierarchy

1. **Model Registry** (`core/llm/config/model_registry.yaml`)
   - Central source of truth for all available models
   - Defines model capabilities, costs, speed, and quality tiers
   - Manages deprecation and migration paths

2. **Environment Variables**
   - Override registry defaults for specific use cases
   - Allow runtime model switching without code changes

3. **Automatic Fallbacks**
   - Registry-based defaults by environment (development, staging, production)
   - Provider-specific fallbacks if registry is unavailable

## Use Cases and Environment Variables

### Main Use Cases

| Use Case | Provider Env Var | Model Env Var | Default |
|----------|------------------|---------------|---------|
| Main Ticket Summary | `TICKET_VIEW_MODEL_PROVIDER` | `TICKET_VIEW_MODEL_NAME` | Per environment |
| Similar Tickets | `TICKET_SIMILAR_MODEL_PROVIDER` | `TICKET_SIMILAR_MODEL_NAME` | Per environment |
| General Summarization | `SUMMARIZATION_MODEL_PROVIDER` | `SUMMARIZATION_MODEL_NAME` | Per environment |
| Real-time Chat | `REALTIME_MODEL_PROVIDER` | `REALTIME_MODEL_NAME` | Per environment |
| Batch Processing | `BATCH_MODEL_PROVIDER` | `BATCH_MODEL_NAME` | Per environment |
| Q&A | `QA_MODEL_PROVIDER` | `QA_MODEL_NAME` | Per environment |
| Analysis | `ANALYSIS_MODEL_PROVIDER` | `ANALYSIS_MODEL_NAME` | Per environment |

### API Keys

- `OPENAI_API_KEY` - Required for OpenAI models
- `ANTHROPIC_API_KEY` - Required for Anthropic/Claude models
- `GOOGLE_API_KEY` or `GEMINI_API_KEY` - Required for Gemini models

## Examples

### Switching Models

```bash
# Use Claude for main ticket summaries
export TICKET_VIEW_MODEL_PROVIDER=anthropic
export TICKET_VIEW_MODEL_NAME=claude-3-5-haiku-20241022

# Use GPT-4 for analysis
export ANALYSIS_MODEL_PROVIDER=openai
export ANALYSIS_MODEL_NAME=gpt-4-turbo

# Use Gemini for similar tickets (fast & cheap)
export TICKET_SIMILAR_MODEL_PROVIDER=gemini
export TICKET_SIMILAR_MODEL_NAME=gemini-1.5-flash
```

### Environment-Based Defaults

The registry defines different defaults per environment:

- **Development**: Optimizes for cost (uses cheaper models)
- **Staging**: Balanced cost and quality
- **Production**: Optimizes for quality

Set environment with: `export ENVIRONMENT=production`

## Model Registry

The registry (`model_registry.yaml`) contains:

- **Providers**: Available model providers and their models
- **Use Cases**: Recommended models for each use case
- **Environments**: Default settings per environment
- **Deprecation Policy**: Migration paths for deprecated models

## Deprecation Handling

### Automatic Migration

When a deprecated model is detected:
1. A warning is logged
2. If a replacement exists, it's automatically used
3. Migration guide is provided in logs

### Check for Deprecated Models

```bash
python -m core.llm.utils.migration_helper --check
```

### Generate Migration Script

```bash
python -m core.llm.utils.migration_helper --generate-script
./migrate_models.sh
```

## Adding New Models

1. Add model to `model_registry.yaml`:
```yaml
providers:
  openai:
    models:
      new-model-name:
        type: "chat"
        capabilities: ["text_generation"]
        cost_tier: "medium"
        speed_tier: "fast"
        quality_tier: "excellent"
        context_window: 128000
        max_tokens: 4096
```

2. Add to use case priorities if needed:
```yaml
use_cases:
  summarization:
    priority_models:
      - provider: "openai"
        model: "new-model-name"
```

3. Restart application to load new configuration

## Troubleshooting

### Model Not Found

If you see "Model not found in registry" warnings:
1. Check spelling of model name in environment variable
2. Verify model exists in `model_registry.yaml`
3. Ensure model is not deprecated

### Automatic Fallback

If specified model is unavailable, the system will:
1. Try replacement model if deprecated
2. Use environment default
3. Use first available model from provider

### Performance

- Model configurations are cached after first load
- Registry is only reloaded on application restart
- API keys are validated during provider initialization