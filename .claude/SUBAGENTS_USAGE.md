# Subagents Usage Guide

## What Are Subagents?

Subagents are specialized AI assistants that you can invoke from within Claude Code. They're defined in `.claude/agents/*.md` files and can be called using the `/agents` command or by explicitly requesting them in conversation.

## Available Subagents

### 1. **explore-base-general**

**Purpose**: General-purpose base repository explorer for project structure, dependencies, and cross-cutting concerns

**When to Use**:
- You need a high-level overview of the base repository
- You want to understand project structure and organization
- You're investigating dependencies or cross-cutting patterns
- You need general information not covered by specialized agents

**Example Usage**:
```
Use explore-base-general to provide an overview of the base repository project structure
```

**What It Provides**:
- Project structure and organization
- Dependency analysis
- Cross-cutting patterns (error handling, logging)
- General file locations and conventions

---

### 2. **explore-base-testing**

**Purpose**: Testing patterns and configurations specialist for pytest, ruff, ESLint, and CI/CD workflows

**When to Use**:
- You're implementing or improving test infrastructure
- You need pytest configuration examples
- You want to understand test organization patterns
- You're setting up CI/CD testing workflows

**Example Usage**:
```
Use explore-base-testing to find pytest configuration patterns in the base repository
```

**What It Provides**:
- Pytest configuration (pytest.ini, pyproject.toml)
- Test organization (unit, integration, e2e)
- Fixtures and test utilities
- Ruff and ESLint configurations
- CI/CD testing workflows

---

### 3. **explore-base-architecture**

**Purpose**: Lambda architecture and design patterns specialist for code organization and function structure

**When to Use**:
- You're designing Lambda function structure
- You need architectural patterns and best practices
- You want to understand code organization approaches
- You're implementing error handling or logging patterns

**Example Usage**:
```
Use explore-base-architecture to analyze Lambda function organization in the base repository
```

**What It Provides**:
- Lambda function directory structure
- Handler patterns and initialization
- Shared library organization
- Design patterns (factory, singleton, etc.)
- Error handling and logging approaches
- Integration patterns (DynamoDB, S3, Step Functions)

---

### 4. **explore-base-docs**

**Purpose**: Documentation structure and style specialist for writing professional, consistent documentation

**When to Use**:
- You're writing or improving documentation
- You need documentation structure templates
- You want to understand formatting conventions
- You're establishing documentation standards

**Example Usage**:
```
Use explore-base-docs to analyze README structure in the base repository
```

**What It Provides**:
- Documentation structure (README, ARCHITECTURE, USER_GUIDE)
- Writing style and tone patterns
- Markdown formatting conventions
- Code block and table formatting
- Docstring patterns

---

### 5. **explore-base-infrastructure**

**Purpose**: Infrastructure and deployment patterns specialist for SAM templates and CloudFormation resources

**When to Use**:
- You're working with SAM templates
- You need CloudFormation resource patterns
- You want to understand IAM policy structures
- You're implementing deployment automation

**Example Usage**:
```
Use explore-base-infrastructure to analyze Lambda function definitions in the SAM template
```

**What It Provides**:
- SAM template structure and organization
- Lambda function resource patterns
- DynamoDB, S3, AppSync resource definitions
- IAM role and policy patterns
- Deployment automation (publish.py)
- Environment variable patterns

---

### 6. **config-pattern-finder**

**Purpose**: Configuration management patterns specialist for DynamoDB operations, GraphQL resolvers, and dynamic forms

**When to Use**:
- You're implementing configuration management systems
- You need DynamoDB read/write patterns
- You want GraphQL resolver examples
- You're building dynamic forms from schema

**Example Usage**:
```
Use config-pattern-finder to show the pattern for reading configuration from DynamoDB
```

**What It Provides**:
- ConfigurationManager implementation patterns
- DynamoDB operations with boto3.resource
- GraphQL operation routing
- Dynamic form rendering from Schema
- Conditional field logic (dependsOn)
- Configuration merging (Custom → Default)

---

## How to Use Subagents

### In Claude Code

**Method 1: Explicit Request** (Recommended for clarity)
```
Use explore-base-testing to find pytest configuration patterns
```

**Method 2: Via /agents Command**
1. **Type `/agents`** to see available subagents
2. **Select the subagent** you want to invoke
3. **Provide your question/request** in the next message

**Method 3: Automatic Invocation**
Claude Code may automatically invoke subagents when it determines they would be helpful for your task.

### Basic Workflow

```
You: Use explore-base-architecture to show me Lambda function organization

Claude: [Invokes explore-base-architecture subagent]
Subagent: [Searches base repo, provides code examples, explains patterns]
Claude: [Summarizes findings and provides recommendations]
```

### Advanced Workflow - Multiple Subagents

```
You: I need to implement testing for my Lambda functions

Claude: [May invoke explore-base-testing for test patterns]
Claude: [May invoke explore-base-architecture for Lambda structure]
Claude: [Synthesizes findings from both agents]
```

## Common Scenarios

### Scenario 1: Implementing Tests

**Goal**: Set up pytest with proper configuration

**Approach**:
```
Use explore-base-testing to find pytest configuration patterns and test organization
```

### Scenario 2: Designing Lambda Functions

**Goal**: Understand Lambda function structure and organization

**Approach**:
```
Use explore-base-architecture to analyze Lambda function organization
```

### Scenario 3: Building Configuration System

**Goal**: Implement DynamoDB-backed configuration management

**Approach**:
```
Use config-pattern-finder to show ConfigurationManager implementation with DynamoDB operations
```

### Scenario 4: Setting Up Infrastructure

**Goal**: Define Lambda functions in SAM template

**Approach**:
```
Use explore-base-infrastructure to show Lambda function resource patterns in SAM template
```

### Scenario 5: Writing Documentation

**Goal**: Create consistent, professional README

**Approach**:
```
Use explore-base-docs to analyze README structure and formatting conventions
```

### Scenario 6: Understanding Project Structure

**Goal**: Get high-level overview of base repository

**Approach**:
```
Use explore-base-general to provide an overview of the base repository project structure
```

## Tips for Effective Use

### 1. **Be Specific**

❌ Bad: "Show me configuration stuff"
✅ Good: "Use config-pattern-finder to show how ConfigurationManager.get_effective_config() merges Custom and Default configurations"

### 2. **State Your Context**

❌ Bad: "How do I do this?"
✅ Good: "I'm implementing a GraphQL resolver for configuration. Use config-pattern-finder to show the operation routing pattern."

### 3. **Ask for Adaptations**

❌ Bad: "Show me the code"
✅ Good: "Use explore-base-architecture to show Lambda handler patterns and explain how to simplify for RAGStack-Lambda"

### 4. **Choose the Right Agent**

Use this quick reference:
- **General questions** → explore-base-general
- **Testing** → explore-base-testing
- **Lambda/code structure** → explore-base-architecture
- **Documentation** → explore-base-docs
- **Infrastructure/SAM** → explore-base-infrastructure
- **Configuration systems** → config-pattern-finder

## Subagent Capabilities

All subagents have access to:
- ✅ **Read** - Read files from disk
- ✅ **Grep** - Search patterns in files
- ✅ **Glob** - Find files by pattern
- ✅ **Bash** - Run shell commands
- ✅ **WebFetch** - Fetch web documentation
- ✅ **WebSearch** - Search for documentation
- ✅ **AskUserQuestion** - Clarify requirements
- ✅ **Context** - Full knowledge of base repository structure

They **cannot**:
- ❌ Modify files (read-only)
- ❌ Deploy or run code
- ❌ Make permanent changes

## Quick Reference Commands

### List Subagents
```
/agents
```

### Explicitly Invoke Subagent
```
Use explore-base-general to [your request]
Use explore-base-testing to [your request]
Use explore-base-architecture to [your request]
Use explore-base-docs to [your request]
Use explore-base-infrastructure to [your request]
Use config-pattern-finder to [your request]
```

## Troubleshooting

**Problem**: Subagent doesn't appear in list
- **Solution**: Ensure `.claude/agents/*.md` files exist in project root
- Check file naming: must end in `.md`
- Verify YAML frontmatter is valid
- Check for 6 files: explore-base-{general,testing,architecture,docs,infrastructure}, config-pattern-finder

**Problem**: Subagent gives generic responses
- **Solution**: Be more specific in your request
- Use explicit invocation: "Use [agent-name] to [specific task]"
- Provide context about what you're implementing

**Problem**: Can't find pattern in base repo
- **Solution**: Start with explore-base-general to locate files
- Then use specialized agent (testing, architecture, etc.) to extract patterns
- For configuration patterns, use config-pattern-finder

**Problem**: Subagent uses wrong model or tools
- **Solution**: Check `.claude/agents/[agent-name].md` frontmatter
- Verify `tools:` and `model:` fields are correct
- All agents should use: `Read, Glob, Grep, Bash, WebFetch, WebSearch, AskUserQuestion`
- All agents should use: `model: haiku`

## Subagent Selection Guide

```
┌─────────────────────────────────────────────────────────┐
│ What do you need?                                       │
├─────────────────────────────────────────────────────────┤
│ Project overview/structure        → explore-base-general│
│ Dependencies, cross-cutting       → explore-base-general│
├─────────────────────────────────────────────────────────┤
│ Test configuration (pytest/ruff)  → explore-base-testing│
│ Test organization, fixtures       → explore-base-testing│
│ CI/CD testing workflows           → explore-base-testing│
├─────────────────────────────────────────────────────────┤
│ Lambda function structure         → explore-base-architecture│
│ Code organization, patterns       → explore-base-architecture│
│ Error handling, logging           → explore-base-architecture│
├─────────────────────────────────────────────────────────┤
│ README, doc structure             → explore-base-docs   │
│ Writing style, formatting         → explore-base-docs   │
│ Docstrings, comments              → explore-base-docs   │
├─────────────────────────────────────────────────────────┤
│ SAM template, CloudFormation      → explore-base-infrastructure│
│ IAM policies, resource patterns   → explore-base-infrastructure│
│ Deployment automation             → explore-base-infrastructure│
├─────────────────────────────────────────────────────────┤
│ ConfigurationManager patterns     → config-pattern-finder│
│ DynamoDB operations               → config-pattern-finder│
│ GraphQL resolvers, routing        → config-pattern-finder│
│ Dynamic forms, Schema rendering   → config-pattern-finder│
└─────────────────────────────────────────────────────────┘
```

## Example Session

```
Developer: I need to implement pytest configuration for my Lambda functions

Claude: I'll help you set up pytest configuration. Let me explore the base repository patterns.

[Invokes explore-base-testing]

Claude: Based on the base repository patterns, here's the recommended pytest configuration:

[Shows pytest.ini or pyproject.toml configuration]
[Explains markers, coverage settings, test organization]
[Provides specific recommendations for RAGStack-Lambda]

Developer: Great! Now show me how to organize the test files

Claude: Let me get the test organization patterns.

[Continues with explore-base-testing or provides from previous findings]

[Shows directory structure, naming conventions, fixture patterns]
```

## Integration with Development Workflow

Subagents are most useful during:

1. **Planning Phase**: Use explore-base-general for architecture overview
2. **Infrastructure Setup**: Use explore-base-infrastructure for SAM templates
3. **Lambda Development**: Use explore-base-architecture for function patterns
4. **Configuration Systems**: Use config-pattern-finder for DynamoDB/GraphQL patterns
5. **Testing Setup**: Use explore-base-testing for test configuration
6. **Documentation**: Use explore-base-docs for README and guide structure

## Summary

Subagents are your **specialized helpers** for working with the base repository:

- 🌐 **explore-base-general** - Project overview and cross-cutting concerns
- 🧪 **explore-base-testing** - Testing patterns and configurations
- 🏗️ **explore-base-architecture** - Lambda architecture and design patterns
- 📚 **explore-base-docs** - Documentation structure and style
- ☁️ **explore-base-infrastructure** - SAM templates and CloudFormation
- ⚙️ **config-pattern-finder** - Configuration management patterns

Use them throughout development to stay aligned with proven patterns from the mature base repository!
