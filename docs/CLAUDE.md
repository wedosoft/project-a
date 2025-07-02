# Documentation & Instructions - CLAUDE.md

## 🎯 Context & Purpose

This is the **Documentation & Instructions** worktree focused on project documentation, AI development guidelines, and architectural specifications for Copilot Canvas. This serves as the central knowledge hub for consistent development across all project components.

**Primary Focus Areas:**
- AI development instructions and guidelines
- Project architecture documentation
- Development patterns and best practices
- Cross-component integration specifications
- Project status tracking and roadmaps

## 📚 Documentation Architecture

### System Overview
```
AI Instructions → Development Guidelines → Implementation
     ↓                    ↓                    ↓
Core Architecture    Specific Patterns    Code Generation
```

### Core Documentation Structure

1. **AI Instructions** (`.github/instructions/`)
   - **Core**: Fundamental architecture and patterns
   - **Development**: Implementation guidelines
   - **Data**: Data processing and workflow patterns
   - **Specialized**: Feature-specific instructions

2. **Project Documentation** (`docs/`)
   - **Status Reports**: Current project state and progress
   - **Architecture Guides**: System design documentation
   - **Development Guides**: Setup and workflow instructions
   - **Roadmaps**: Future development planning

### Key Design Principles

- **Hierarchical Reference**: Quick reference → Detailed guidance → Implementation
- **Cross-linking**: Interconnected documentation with clear navigation
- **AI-Optimized**: Structured for AI assistant comprehension and reference
- **Version Controlled**: All changes tracked with reasoning and context
- **Modular**: Separate concerns for easier maintenance and updates

## 🏗️ AI Instructions Structure

### Core Instructions (`core/`)

1. **Quick Reference** (`quick-reference.instructions.md`)
   - Essential patterns and checklists
   - Immediate reference for common tasks
   - Architecture decision summary

2. **Global Guidelines** (`global.instructions.md`)
   - Project-wide development principles
   - Coding standards and conventions
   - Error handling patterns

3. **System Architecture** (`system-architecture.instructions.md`)
   - Complete system design overview
   - Component interaction patterns
   - Integration specifications

4. **Multi-tenant Security** (`multitenant-security.instructions.md`)
   - Security patterns and requirements
   - Data isolation strategies
   - Authentication and authorization

5. **Performance Optimization** (`performance-optimization.instructions.md`)
   - Performance patterns and strategies
   - Caching implementations
   - Optimization guidelines

### Development Instructions (`development/`)

1. **Backend Patterns** (`backend-implementation-patterns.instructions.md`)
   - FastAPI development patterns
   - Database integration patterns
   - API design principles

2. **Frontend Patterns** (`fdk-development-patterns.instructions.md`)
   - FDK development guidelines
   - JavaScript module patterns
   - UI/UX implementation

3. **API Architecture** (`api-architecture-file-structure.instructions.md`)
   - API structure and organization
   - Endpoint design patterns
   - Documentation standards

4. **Error Handling** (`error-handling-debugging.instructions.md`)
   - Error handling strategies
   - Debugging techniques
   - Logging patterns

5. **Coding Principles** (`coding-principles-checklist.instructions.md`)
   - Code quality standards
   - Review checklists
   - Best practice guidelines

### Data Instructions (`data/`)

1. **Data Workflow** (`data-workflow.instructions.md`)
   - Complete data processing pipeline
   - Ingestion patterns
   - Storage strategies

2. **Vector Database** (`vector-database-operations.instructions.md`)
   - Qdrant integration patterns
   - Vector operations
   - Performance optimization

3. **LLM Integration** (`llm-integration-patterns.instructions.md`)
   - LLM provider management
   - Prompt engineering
   - Response handling

## 📋 Project Documentation

### Status Documentation (`docs/`)

1. **Master Status** (`MASTER_STATUS.md`)
   - Overall project progress
   - Completed milestones
   - Current development state

2. **Current Issues** (`CURRENT_ISSUES.md`)
   - Active problems and solutions
   - Known limitations
   - Resolution tracking

3. **Development Guide** (`DEVELOPMENT_GUIDE.md`)
   - Setup instructions
   - Workflow guidelines
   - Tool configurations

4. **Next Session Guide** (`NEXT_SESSION_GUIDE_*.md`)
   - Session transition information
   - Immediate action items
   - Context preservation

### Architecture Documentation

1. **System Design** - High-level architecture overview
2. **Database Schema** - Data model specifications
3. **API Specifications** - Endpoint documentation
4. **Integration Patterns** - Cross-component communication

## 🔍 AI Reference Patterns

### Efficient AI Consultation

**3-Tier Reference Structure:**
```
Level 1: Quick Reference → Immediate answers
Level 2: Category Docs → Focused guidance  
Level 3: Detailed Files → Implementation specifics
```

**Usage Patterns:**
- **New Feature Development**: Core → Development → Specialized
- **Bug Fixing**: Error Handling → Relevant Category → Implementation
- **Architecture Changes**: System Architecture → All Related Docs
- **Performance Issues**: Performance Optimization → Specific Patterns

### AI Prompt Optimization

**Effective Reference Format:**
```markdown
Context: [Brief description of task/issue]
Reference: [Specific instruction file sections]
Constraints: [Technical limitations or requirements]
Goal: [Desired outcome with success criteria]
```

## 🚀 Documentation Commands

### Environment Setup
```bash
# Generate frontend API documentation
cd frontend
npm run docs:generate
npm run docs:serve

# View documentation locally
open frontend/docs/api/index.html

# Validate instruction completeness
find .github/instructions -name "*.md" | wc -l
```

### Documentation Maintenance
```bash
# Update project status
# Edit docs/MASTER_STATUS.md with latest progress

# Create new session guide
# Copy and update docs/NEXT_SESSION_GUIDE_template.md

# Validate cross-references
# Check all [link](file.md) references are valid

# Generate instruction index
# Update .github/instructions/INDEX.md
```

## 📁 Directory Structure

```
Documentation Root/
├── .github/instructions/    # AI Development Instructions
│   ├── INDEX.md            # Master instruction index
│   ├── core/               # Core architecture patterns
│   │   ├── quick-reference.instructions.md
│   │   ├── global.instructions.md
│   │   ├── system-architecture.instructions.md
│   │   ├── multitenant-security.instructions.md
│   │   └── performance-optimization.instructions.md
│   ├── development/        # Implementation patterns
│   │   ├── backend-implementation-patterns.instructions.md
│   │   ├── fdk-development-patterns.instructions.md
│   │   ├── api-architecture-file-structure.instructions.md
│   │   ├── error-handling-debugging.instructions.md
│   │   └── coding-principles-checklist.instructions.md
│   ├── data/              # Data processing patterns
│   │   ├── data-workflow.instructions.md
│   │   ├── vector-database-operations.instructions.md
│   │   └── llm-integration-patterns.instructions.md
│   └── specialized/       # Feature-specific patterns
├── docs/                  # Project Documentation
│   ├── MASTER_STATUS.md   # Overall project status
│   ├── DEVELOPMENT_GUIDE.md
│   ├── CURRENT_ISSUES.md
│   ├── ROADMAP.md
│   └── architecture/      # Architecture specs
└── archived_docs/         # Historical documentation
```

## 🔧 Documentation Standards

### Instruction File Format
```markdown
# Title - Descriptive Name

## 🎯 Purpose & Scope
[Clear description of what this covers]

## ⚡ Quick Reference
[Immediate action items and key points]

## 📋 Detailed Guidelines
[Comprehensive implementation guidance]

## 🔗 Related References
[Cross-links to other relevant instructions]

## ✅ Validation Checklist
[Items to verify implementation]
```

### Status Documentation Format
```markdown
# Status Report Title

## 📊 Progress Overview
[Current completion percentages]

## ✅ Completed Items
[What's been finished]

## 🚧 In Progress
[Current active work]

## ⏭️ Next Steps
[Immediate priorities]

## 🚨 Issues & Blockers
[Problems needing attention]
```

## 🎯 AI Integration Patterns

### Context-Aware Assistance
```markdown
**For AI Assistants:**
1. Always reference relevant instruction files
2. Follow established patterns consistently
3. Update documentation when making changes
4. Cross-reference related components
5. Maintain architectural integrity
```

### Documentation-Driven Development
1. **Plan**: Review architecture docs and patterns
2. **Implement**: Follow specific instruction guidelines
3. **Document**: Update status and add new patterns
4. **Validate**: Check against established criteria
5. **Integrate**: Ensure cross-component compatibility

## 🔗 Cross-Component Integration

### Backend ↔ Frontend
- API specification consistency
- Data format standardization
- Error handling alignment
- Security pattern coordination

### Documentation ↔ Implementation
- Instruction adherence validation
- Pattern implementation verification
- Status tracking accuracy
- Architecture compliance checking

## 📚 Key Files to Know

### AI Instructions
- `.github/instructions/INDEX.md` - Master instruction index
- `.github/instructions/core/quick-reference.instructions.md` - Essential patterns
- `.github/instructions/core/global.instructions.md` - Global development rules

### Project Documentation
- `docs/MASTER_STATUS.md` - Current project state
- `docs/DEVELOPMENT_GUIDE.md` - Setup and workflow
- `docs/NEXT_SESSION_GUIDE_*.md` - Session transition info

### Architecture Specifications
- `.github/instructions/core/system-architecture.instructions.md` - System design
- `.github/instructions/development/*` - Implementation patterns
- `.github/instructions/data/*` - Data processing patterns

## 🔄 Documentation Workflow

1. **Review Current State**: Check latest status documents
2. **Reference Instructions**: Use AI instructions for guidance
3. **Implement Changes**: Follow documented patterns
4. **Update Documentation**: Reflect changes in relevant docs
5. **Cross-Reference**: Ensure all related docs are consistent
6. **Validate**: Check against established criteria

### Maintenance Schedule
- **Daily**: Update status for active development
- **Weekly**: Review and update issue tracking
- **Sprint**: Comprehensive status and roadmap updates
- **Major Changes**: Architecture and instruction updates

---

*This worktree focuses exclusively on documentation and AI instructions. For implementation, switch to the appropriate backend or frontend worktree while referencing these guidelines.*
