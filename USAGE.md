# Skills Directory Usage Guide

## Overview
The `skills/` directory is a fully self-contained, AI-agent-optimized knowledge base of Alliander's development patterns, best practices, and organization-specific implementations. It can be used independently without access to the original example projects.

## What Makes It Self-Contained?

### No External Dependencies
- All patterns are documented with complete context
- Code examples are included where needed
- Configuration details are fully specified
- No references to specific example project files

### Production-Validated
Every skill document includes a "Source Projects" section confirming that the pattern has been validated against production implementations. This provides confidence without requiring access to the original source code.

### Complete Information
Each skill includes:
- Overview and key concepts
- Alliander-specific implementation patterns
- Decision criteria (when to use)
- Common pitfalls and how to avoid them
- Configuration requirements
- Cross-references to related skills

## How to Use This Knowledge Base

### For Starting a New Project

1. **Choose your technology stack**
   - Read `patterns-project-structure.md` for language-specific guidance
   - Select appropriate frontend/backend skill documents

2. **Set up project structure**
   - Follow the relevant skill document (e.g., `backend-fastapi-structure.md`)
   - Use the configuration examples provided
   - Apply Alliander-specific patterns

3. **Configure infrastructure**
   - Start with `infra-aws-cdk-basics.md`
   - Use `org-alliander-cloud-cdk-libs.md` for Alliander constructs
   - Follow `infra-aws-cdk-multi-environment.md` for multi-env setup

4. **Set up CI/CD**
   - Implement `cicd-github-actions-autobahn.md` patterns
   - Configure `cicd-branch-based-deployment.md` if needed
   - Set up `cicd-gitops-integration.md` for GitOps workflow

5. **Configure deployment**
   - For Kubernetes: `k8s-helm-chart-structure.md` and related k8s skills
   - For GitOps: `gitops-argocd-app-of-apps.md` and related gitops skills
   - Apply security patterns from `security-*` skills

### For AI Agents

The skills directory is optimized for AI agent retrieval and usage:

**Category-Based Filtering**
```
frontend-*    : Frontend technologies
backend-*     : Backend frameworks
infra-*       : Infrastructure as Code
container-*   : Docker and containerization
k8s-*         : Kubernetes
gitops-*      : GitOps patterns
cicd-*        : CI/CD pipelines
security-*    : Security patterns
devops-*      : DevOps tools
org-*         : Alliander-specific tools
patterns-*    : Cross-cutting patterns
```

**Navigation Strategy**
1. Start with the skill matching the user's query
2. Follow "Related Skills" for comprehensive understanding
3. Check "When to Use" for decision support
4. Review "Common Pitfalls" for error prevention

**Information Extraction**
- All code examples are production-ready
- Configuration sections provide exact values
- Alliander-Specific Patterns section contains unique implementations
- No common knowledge is included (optimized for expert agents)

### For Developers

**Quick Reference**
- Use `skills/README.md` for navigation and quick reference
- Search by technology name or pattern
- Follow related skills for complete understanding

**Implementation Templates**
- Each skill provides implementation patterns
- Code examples show Alliander-specific configurations
- Configuration sections provide exact setup details

**Decision Support**
- "When to Use" sections help choose between alternatives
- "Common Pitfalls" prevent common mistakes
- Related skills show the complete picture

## Key Differences from Example Projects

### Example Projects (examples/ directory)
- Complete, runnable applications
- Specific implementations for specific use cases
- May include legacy patterns or experimental features
- Require understanding of full project context

### Skills Directory (skills/ directory)
- Extracted, generalized patterns
- Focused on reusable knowledge
- Production-validated best practices
- Self-contained with complete context
- Optimized for quick retrieval and application

## Can You Delete the Examples Directory?

**Yes**, if you only need the patterns and best practices. The skills directory is fully self-contained.

**Keep examples if**:
- You want to see complete, working implementations
- You need to understand how patterns work together in a full application
- You want to run and test the code locally
- You're learning and want concrete examples

**Use skills only if**:
- You're building new projects and need patterns
- You're an AI agent optimizing for fast retrieval
- You want production-validated best practices
- You need Alliander-specific configurations

## Maintenance

### Updating Skills
When patterns evolve or new patterns emerge:
1. Update the relevant skill document
2. Maintain the consistent structure
3. Update version numbers in Configuration sections
4. Update the "Source Projects" validation statement
5. Update cross-references if needed

### Adding New Skills
1. Follow naming convention: `{category}-{technology}-{aspect}.md`
2. Use the standard document structure
3. Include only non-obvious information
4. Add cross-references to related skills
5. Update `skills/README.md` with the new skill

## Examples of Usage

### Example 1: Building a FastAPI Application
```
1. Read: backend-fastapi-structure.md
2. Read: devops-code-quality.md (for ruff + mypy)
3. Read: backend-fastapi-deployment.md
4. Read: infra-cdk-ecs-fargate.md
5. Read: cicd-github-actions-autobahn.md
```

### Example 2: Setting Up GitOps
```
1. Read: gitops-repository-structure.md
2. Read: gitops-argocd-app-of-apps.md
3. Read: gitops-multi-environment.md
4. Read: k8s-helm-chart-structure.md
5. Read: cicd-gitops-integration.md
```

### Example 3: Angular Frontend with ATP
```
1. Read: frontend-angular-standalone-components.md
2. Read: org-alliander-template-package.md
3. Read: org-alliander-atp-components.md
4. Read: frontend-angular-routing.md
5. Read: frontend-angular-ssr.md (if needed)
```

## Benefits of This Approach

### For Teams
- Consistent patterns across projects
- Faster onboarding for new developers
- Reduced decision fatigue
- Clear best practices

### For AI Agents
- Fast pattern retrieval
- No need to analyze full projects
- Clear decision criteria
- Production-validated patterns

### For Projects
- Faster project setup
- Fewer mistakes
- Alliander-specific configurations ready to use
- Clear upgrade paths

## Questions?

If you need clarification on any pattern or have questions about usage:
1. Check the "Related Skills" section for additional context
2. Review the "Common Pitfalls" section for known issues
3. Consult the "When to Use" section for decision criteria
4. Refer to the "Configuration" section for exact setup details

All patterns are production-validated and ready to use in your projects.
