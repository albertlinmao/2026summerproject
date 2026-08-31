# Free AI Vibe Coding: Building Software Without Paying for Every AI Request

**A practical experiment with OpenCode, OpenCode Zen, Google models, and local AI**

AI-assisted software development has changed the way developers build applications. Tools such as AI coding agents can read a codebase, generate code, modify multiple files, run tests, debug problems, and even implement features from a natural-language description.

It sounds like the future of software development.

But there is a problem.

**AI Vibe Coding is not necessarily cheap. And it is not necessarily fast.**

The more I use AI coding agents, the more I realize that the interesting problem is not simply finding the most powerful model. The real challenge is building a development workflow that balances **cost, speed, quality, and developer control**.

This blog is an experiment in finding that balance.

---

## What Is AI Vibe Coding?

Vibe coding is a development style where a developer describes what they want in natural language and allows an AI coding agent to implement much of the solution.

Instead of manually writing every class, API, database query, test, and UI component, the developer works more like an architect and technical reviewer.

A typical workflow might look like this:

```text
Developer
    │
    │ Natural-language requirements
    ▼
AI Coding Agent
    │
    ├── Understand codebase
    ├── Plan implementation
    ├── Modify code
    ├── Run tests
    ├── Debug
    └── Refactor
    │
    ▼
Working Software
```

This can dramatically increase development speed.

But it also creates a new problem:

**Every step may require AI inference.**

And inference costs money and time.

---

# The Reality: AI Vibe Coding Is Not Free

It is easy to think that AI coding means:

> "I describe the application, AI builds it, and I don't have to code anymore."

Real projects are not like that.

A serious AI coding session can involve many model requests:

```text
Read repository
      ↓
Understand architecture
      ↓
Analyze requirements
      ↓
Create implementation plan
      ↓
Modify files
      ↓
Run tests
      ↓
Analyze failures
      ↓
Fix implementation
      ↓
Run tests again
      ↓
Refactor
      ↓
Review
```

A single feature can therefore result in many AI interactions.

For a large project, the context can also become enormous.

The result is that AI-assisted development can become expensive, especially when using premium models continuously.

---

# AI Vibe Coding Can Also Be Slow

Cost is only half of the problem.

**Latency matters.**

A developer can spend a surprising amount of time waiting for an AI agent.

For example:

```text
Developer thinks        10 seconds
AI analyzes code        60 seconds
AI generates changes    90 seconds
Tests run               30 seconds
AI analyzes failure     60 seconds
AI fixes code           90 seconds
```

The developer may spend several minutes waiting for a relatively small change.

This becomes especially noticeable when the AI agent repeatedly performs large-context operations.

The problem isn't necessarily that the model is slow.

The problem is that **we are using an expensive and powerful model for tasks that don't always require it.**

---

# The Idea: Use the Right Model for the Job

This leads to the main idea behind this blog:

> **Don't ask which AI model is the best. Ask which AI model is best for this task.**

A simple code change doesn't necessarily require the strongest reasoning model.

Generating boilerplate doesn't require a premium model.

Writing a simple unit test doesn't require the largest context window.

On the other hand, a difficult architectural problem or complicated debugging session may justify using a stronger model.

The goal is therefore to build a **multi-model AI development workflow**.

---

# My Free AI Vibe Coding Stack

The experiment starts with several different AI sources:

```text
                    OpenCode
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
     OpenCode Zen   Google       Local Models
                    Models
          │            │            │
          └────────────┼────────────┘
                       ▼
                 AI Development
```

The idea is not to commit to one model.

Instead, I want to be able to switch models depending on the work.

### OpenCode

OpenCode acts as the coding agent and development interface.

The important concept is that the coding workflow can be separated from the underlying model.

That makes it possible to experiment with different models without completely changing the development environment.

### OpenCode Zen

OpenCode Zen provides another model option within the OpenCode ecosystem.

When a free or low-cost model is sufficient, it can be used instead of consuming a premium model.

The exact availability, limits, and pricing can change, so each experiment should be evaluated against the current offering.

### Google Models

Google's Gemini models provide another option for cloud-based AI coding.

They are particularly interesting for experimenting with a free or low-cost development workflow.

Again, the important point is not that one particular model is always the best.

The point is having another model available when it makes sense.

### Local Models

Local models are the most interesting part of the experiment.

Instead of sending a request to a cloud provider, a developer can run an LLM locally using tools such as Ollama or other local inference environments.

The architecture becomes:

```text
Developer
    │
    ▼
OpenCode
    │
    ├──────── Cloud Model
    │
    ├──────── Google Model
    │
    ├──────── OpenCode Zen
    │
    └──────── Local LLM
                 │
                 ▼
             Developer PC
```

Local models don't eliminate the cost of hardware or electricity, but they can eliminate per-request API costs.

They also provide an important privacy advantage for source code that a developer may not want to send to a cloud service.

---

# Free Does Not Mean Unlimited

One of the first lessons of this experiment is:

> **Free AI is not the same thing as unlimited AI.**

There are several different meanings of "free."

| Approach                 |   Direct AI Cost | Typical Strength | Main Trade-off      |
| ------------------------ | ---------------: | ---------------- | ------------------- |
| Free cloud model         | $0 within limits | Medium           | Usage limits        |
| OpenCode Zen free option | $0 within limits | Varies           | Availability/limits |
| Google free tier         | $0 within limits | Medium–High      | Quotas              |
| Local model              |   $0 per request | Varies           | Hardware            |
| Premium cloud model      |              $$$ | High             | Cost                |

The goal is not to pretend that AI has no cost.

The goal is to **minimize unnecessary cost**.

---

# Model Switching Is an Engineering Skill

I believe model switching will become an important AI development skill.

A practical workflow might look like this:

```text
                    Coding Task
                         │
                         ▼
                How difficult is it?
                         │
             ┌───────────┼───────────┐
             │           │           │
           Easy       Medium       Hard
             │           │           │
             ▼           ▼           ▼
          Local       Free Cloud   Stronger
          Model         Model        Model
             │           │           │
             └───────────┼───────────┘
                         ▼
                      Review
```

For example:

### Simple tasks

Use a local or free model for:

- CRUD code
- Simple DTOs
- Basic unit tests
- Documentation
- Boilerplate
- Simple refactoring

### Medium-complexity tasks

Use a stronger free cloud model for:

- API implementation
- Angular components
- Database queries
- Integration tests
- Moderate debugging

### Difficult tasks

Use a stronger model when necessary:

- Architecture decisions
- Complex debugging
- Large refactoring
- Difficult concurrency problems
- Security-sensitive design
- Understanding unfamiliar systems

The key is to **spend expensive AI reasoning only when it provides meaningful value.**

---

# The Real Metric Isn't Token Cost

It is tempting to compare models based on price per token.

That isn't enough.

Suppose Model A costs nothing but takes five minutes and requires three rounds of corrections.

Model B costs a few cents but produces a correct implementation in one minute.

Which one is cheaper?

The answer depends on the developer's time.

So I want to measure AI coding using several dimensions:

```text
AI Coding Efficiency

        Cost
         +
      Waiting Time
         +
 Developer Intervention
         +
      AI Iterations
         +
     Defect Rate
         +
    Final Quality
```

A better metric might be:

> **Useful software delivered per dollar and per developer hour.**

That is much more meaningful than simply asking how many tokens a model consumed.

---

# The $0 AI Coding Experiment

One of the goals of this blog is to answer a simple question:

> **How much real software can I build using a $0 AI coding budget?**

Not a toy application.

Not a five-file demo.

A real application.

The experiment will use technologies such as:

- OpenCode
- OpenCode Zen
- Google AI models
- Local LLMs
- Angular
- Python
- FastAPI
- PostgreSQL
- Supabase
- Docker
- Git
- Automated testing

The goal is to build applications that require real engineering work.

---

# A Real Project Is the Best Test

For example, an AI-assisted application might contain:

```text
Frontend
    Angular
       │
       ▼
Backend
    FastAPI
       │
       ▼
Database
    PostgreSQL / Supabase
       │
       ▼
Analytics
       │
       ▼
Deployment
```

The project may require:

- Requirements
- Architecture
- Database modeling
- API design
- Authentication
- UI development
- Testing
- Error handling
- Logging
- Deployment
- Documentation

This is where AI vibe coding becomes interesting.

The question isn't:

> "Can AI generate code?"

Of course it can.

The real questions are:

> Can AI maintain a coherent architecture?

> Can different models work on the same codebase?

> Can a local model handle useful development tasks?

> When does a free model become too slow?

> When is paying for a stronger model worth it?

---

# Measuring the Experiment

For each project or feature, I want to record a small set of metrics.

| Metric                 | What it tells us                          |
| ---------------------- | ----------------------------------------- |
| Model                  | Which AI was used                         |
| Task                   | What the AI was asked to do               |
| Time                   | How long the interaction took             |
| Iterations             | How many attempts were required           |
| Developer intervention | How much manual coding was needed         |
| Bugs                   | Problems introduced                       |
| Final quality          | Whether the implementation was acceptable |
| Cost                   | Approximate AI cost                       |

This creates a much more useful picture of AI coding performance.

---

# What I Don't Want This Blog to Be

This is not going to be another blog that claims:

> "AI will replace software developers."

It also isn't going to claim:

> "You can build everything for free."

Both statements are too simplistic.

AI coding agents are powerful tools, but they have limitations.

They can generate incorrect code.

They can misunderstand requirements.

They can make unnecessary architectural changes.

They can consume large amounts of context.

They can become slow.

And sometimes the developer spends more time correcting AI-generated code than writing the code manually.

The objective is to understand **where AI actually provides leverage**.

---

# The Developer Still Matters

AI vibe coding changes the developer's role.

The developer increasingly becomes responsible for:

- Defining requirements
- Establishing architecture
- Setting constraints
- Reviewing generated code
- Validating behavior
- Designing tests
- Managing technical debt
- Choosing the right model
- Deciding when AI should not be used

This means that AI coding does not eliminate engineering.

It makes **engineering judgment more important**.

---

# The Future Workflow

I expect the AI development workflow to evolve toward something like this:

```text
                Developer
                    │
                    ▼
             Requirements
                    │
                    ▼
              AI Coding Agent
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
       Local      Free      Premium
       Model      Cloud      Model
          │         │         │
          └─────────┼─────────┘
                    ▼
              Generated Code
                    │
                    ▼
                 Tests
                    │
                    ▼
                 Review
                    │
                    ▼
              Production
```

The developer doesn't need to choose one AI forever.

The developer chooses the **best available tool for each step**.

---

# What I Hope to Learn

Through this blog, I want to answer practical questions:

1. How much can I really build with free AI?
2. How much does AI coding actually cost?
3. How much time do I spend waiting for AI?
4. Are local models useful for professional development?
5. Which tasks should use local models?
6. Which tasks justify stronger cloud models?
7. How effective is OpenCode as a model-independent coding agent?
8. Can multiple AI models work effectively on the same project?
9. How much developer intervention is really required?
10. Can a carefully designed workflow outperform simply subscribing to the most expensive AI coding tool?

---

# The Goal

The goal isn't to eliminate the cost of software development.

The goal is to eliminate **unnecessary AI cost and unnecessary AI waiting time**.

A good AI coding workflow should give developers choices:

```text
             Need speed?
                  │
             ┌────┴────┐
             │         │
          Local     Cloud
             │         │
          Free      Strong
             │         │
             └────┬────┘
                  │
              Choose based
                on task
```

The most powerful AI model isn't always the best choice.

The cheapest model isn't always the best choice either.

And the fastest model isn't necessarily the best.

The real objective is finding the right balance between:

**Cost + Speed + Quality + Developer Productivity**

That's what this experiment is about.

---

# Welcome to Free AI Vibe Coding

I'll use this blog to document the experiments, the successes, the failures, the surprising results, and the lessons learned while building real software with AI.

The tools and models will change.

The workflow will evolve.

Some experiments will fail.

That's part of the point.

Rather than asking whether AI vibe coding is free, I'm going to ask a more useful question:

> **How can we make AI-assisted software development dramatically cheaper and faster without sacrificing engineering quality?**

Let's find out.
