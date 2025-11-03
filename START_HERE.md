# RAGStack-Lambda: Start Here 🚀

**Welcome!** This guide will help you navigate the deployment options for RAGStack-Lambda.

---

## What Is This?

RAGStack-Lambda is a serverless document processing system with **optional** conversational chat.

**You can**:
- Deploy just the core system (search only) - **Path A** ⚡
- Deploy the full system (search + chat) - **Path B** 🎯
- Start with Path A, add chat later whenever you want ✨

---

## Quick Decision Tree

```
Do you want chat in your system?

    ├─ NO (Launch MVP fast)
    │  └─→ Path A: Core Only
    │       ↓
    │       Go to: project root CLAUDE.md
    │       Run: python publish.py
    │       Time: 2-4 hours
    │
    └─ YES (Full featured from start)
       └─→ Path B: Core + Chat
            ↓
            Go to: docs/plans/DEPLOYMENT_OPTIONS.md
            Time: 6-8 hours total
```

---

## Reading Order

### Everyone: Start Here
1. **This file** (you're reading it) ← **You are here**
2. **docs/plans/DEPLOYMENT_OPTIONS.md** ← Read this next to choose your path

### For Path A (MVP)
3. Stop here! Jump to **CLAUDE.md** in project root

### For Path B (Chat)
3. **docs/plans/OPTIONAL_CHAT_STRATEGY.md** (understand the strategy)
4. **docs/plans/Phase-0.md** (understand Amplify architecture)
5. **docs/ARCHITECTURE_OPTIONAL_STACKS.md** (deep dive on stack interaction)
6. **docs/plans/Phase-1.md** through **Phase-3.md** (implementation)

---

## File Map

```
RAGStack-Lambda/
├── CLAUDE.md (existing)               ← For Path A or core setup
├── publish.py (existing)              ← Deployment script
├── template.yaml (existing)           ← SAM template
│
├── docs/
│   ├── START_HERE.md                  ← You are here
│   ├── ARCHITECTURE_OPTIONAL_STACKS.md ← Technical reference
│   │
│   └── plans/
│       ├── README.md                   ← Overview of all phases
│       ├── DEPLOYMENT_OPTIONS.md       ← Choose Path A or B
│       ├── OPTIONAL_CHAT_STRATEGY.md   ← High-level strategy
│       ├── IMPLEMENTATION_SUMMARY.md   ← What we've built
│       │
│       ├── Phase-0.md (OPTIONAL)       ← Amplify setup
│       ├── Phase-1.md (OPTIONAL)       ← Chat backend
│       ├── Phase-2.md (OPTIONAL)       ← Chat frontend
│       └── Phase-3.md (OPTIONAL)       ← Testing & deploy
│
└── amplify/ (for Path B)               ← Created by you
    ├── data/resource.ts               ← Amplify schema (you'll write)
    └── functions/extractSources.ts    ← Custom logic (you'll write)
```

---

## The Two Paths Explained

### Path A: MVP Launch 🚀
```
Deploy This:
  SAM Stack (Document pipeline + Search)

What You Get:
  ✅ Document upload & processing
  ✅ Automatic OCR
  ✅ Embedding generation
  ✅ Document search
  ✅ Web UI
  ❌ No chat

Time: 2-4 hours
Cost: $80-150/month
```

### Path B: Full Featured 🎯
```
Deploy This:
  SAM Stack (core) + Amplify Stack (chat)

What You Get:
  ✅ Everything from Path A
  ✅ Chat interface
  ✅ Multi-turn conversations
  ✅ Source attribution
  ✅ Persistent history
  ✅ Web UI with both

Time: 6-8 hours (core + chat)
Cost: $85-160/month
```

---

## Infrastructure: Very Simple

```
                    Bedrock KB
                   (Shared)
                      ↑
        ┌─────────────┴──────────────┐
        │                            │
    SAM Stack                    Amplify Stack
    (Required)                   (Optional)

    Search Feature         Chat Feature
    (Always available)     (Optional add-on)
```

---

## Next: Make Your Decision

### Choose Path A?
→ Go to **CLAUDE.md** (project root) for existing setup guide

### Choose Path B?
→ Read **docs/plans/DEPLOYMENT_OPTIONS.md** for detailed comparison

---

## Key Facts

| Fact | Benefit |
|------|---------|
| **Two separate stacks** | Deploy/update/delete independently |
| **Same Bedrock KB** | Documents indexed once, used by both |
| **Optional deployment** | Launch MVP now, add chat later |
| **All serverless** | No infrastructure to manage |
| **On-demand pricing** | Pay only for usage, scales automatically |
| **Can remove chat** | Just delete Amplify stack, core keeps running |

---

## Architecture Decision

We decided:
- ✅ **SAM stack** handles core document pipeline (Python, existing)
- ✅ **Amplify stack** handles chat feature (TypeScript, optional)
- ✅ **Both share** same Bedrock Knowledge Base
- ✅ **Each can** deploy/update/delete independently
- ✅ **No duplication** of embeddings or vector storage
- ✅ **Cost-effective** - pay for what you use

This gives you **maximum flexibility** with **minimum complexity**.

---

## Decision Time

**Are you ready?** Pick one:

### Option A: I want to launch MVP fast
```
1. Read: CLAUDE.md (project root)
2. Run: python publish.py --project-name myapp --admin-email user@e.com --region us-east-1
3. Done! (~2-4 hours)
4. Later: Add chat if desired
```

### Option B: I want the full system now
```
1. Read: docs/plans/DEPLOYMENT_OPTIONS.md
2. Then: docs/plans/Phase-0.md
3. Follow: Phases 1-3 for chat implementation
4. Done! (~6-8 hours)
```

---

## Questions?

- **"How do I deploy?"** → See your chosen path above
- **"Can I change my mind?"** → Yes! Deploy Path A first, add Path B later
- **"What if chat fails?"** → Core system keeps working, just delete chat stack
- **"How much does this cost?"** → Path A: $80-150, Path B: $85-160 (light usage)
- **"What's the difference?"** → Read DEPLOYMENT_OPTIONS.md

---

## You're Ready! 🎉

Choose your path and proceed to the next document.

**Questions before you decide?** That's what the detailed documents are for - they explain everything.

---

**Next Step**: Read **docs/plans/DEPLOYMENT_OPTIONS.md** to confirm your choice
