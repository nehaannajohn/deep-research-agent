# Research Report
**Query:** Map the research landscape of multi-agent LLM systems. Produce a structured report that includes a visual taxonomy or design graph showing the major architectural patterns, how they relate, and where the open problems are.

## Summary
The research landscape of multi-agent LLM systems encompasses various architectural patterns, their relationships, and open problems. Major architectural patterns include centralized and decentralized architectures [c0]. This report outlines the taxonomy of these patterns and highlights key challenges.


## Architecture

```mermaid
graph LR
    subgraph Architectural_Patterns
        Centralized -->|employs|> Hierarchical
        Centralized --> Supervisor_Worker
        Decentralized -->|employs|> Collaborative
        Decentralized --> Swarm
        Hybrid -->|combines|> Supervisor_Worker
        Hybrid -->|combines|> Swarm
    end

    subgraph Pattern_Relationships
        Supervisor_Worker -->|related to|> Hierarchical
        Graph_Orchestration -->|effective in|> Production_Environments
        Hierarchical -->|effective in|> Production_Environments
        Router -->|classifies input|> Specialized_Agents
        Skills -->|loads prompts|> On_demand_Knowledge
        Handoffs -->|changes agent|> Conversation_Context
    end

    subgraph Open_Problems
        Scalability
        Security
        Multimodal_Integration
        Managing_Memory_Safely
        Ensuring_Shared_Knowledge_Integrity
        Recalling_Past_Interactions
        Detecting_Mitigating_Hallucinations
        Identifying_Optimal_Communication_Patterns
        Profiling_Selecting_Agent_Structures
        Pruning_Unnecessary_Links
        Designing_Microstructures
    end

    subgraph Taxonomy
        Centralized
        Decentralized
        Hybrid
        Hierarchical
        Supervisor_Worker
        Swarm
        Collaborative
        Graph_Orchestration
        Router
        Skills
        Handoffs
    end

    subgraph Communication_Architectures
        Flat
        Hierarchical_Comm
        Team
        Society
        Hybrid_Comm
    end

    subgraph Topological_Patterns
        Chain
        Route
        Parallel
        Orchestrate
        Loop
        Hierarchy
    end

    Architectural_Patterns -->|includes|> Taxonomy
    Pattern_Relationships -->|relates|> Taxonomy
    Open_Problems -->|challenges|> Taxonomy
    Communication_Architectures -->|part of|> Taxonomy
    Topological_Patterns -->|part of|> Taxonomy
```

## Architectural Patterns
Multi-agent LLM systems employ several architectural patterns. Centralized systems use hierarchical patterns with a central supervisor delegating tasks to specialized agents [c1]. Decentralized systems utilize collaborative patterns where autonomous agents communicate directly [c2]. Key patterns include [c3]:
- Subagents
- Skills
- Handoffs
- Routers

Other configurations include Supervisor, Swarm, Hierarchical, and Single Information Environment (SIE) architectures [c4], as well as Flat, Hierarchical, Team, Society, and Hybrid communication architectures [c5]. Topological patterns comprise Chain, Route, Parallel, Orchestrate, Loop, and Hierarchy structures [c6].

## Relationships Between Patterns
Patterns such as supervisor-worker and hierarchical are related through their supervisory or orchestration mechanisms [c8]. Graph orchestration and hierarchical patterns are effective in production environments [c10]. Hybrid patterns, like supervisor-plus-pipeline and supervisor-plus-swarm, are common in production systems [c15]. Most production systems are compositions of two or three canonical patterns [c14].

## Open Problems
Several challenges persist in multi-agent LLM systems, including [c20]:
- Scalability
- Security
- Multimodal integration

Other open problems involve [c16]:
- Managing memory safely and securely
- Ensuring the integrity of shared knowledge [c18]
- Recalling contextually relevant past interactions [c19]
- Detecting and mitigating hallucinations [c23]
- Identifying optimal macro-level communication patterns [c26]
- Automatically profiling and selecting effective agent structures [c27]
- Pruning unnecessary links [c28]
- Designing micro-structures for maximized performance [c29]

## Visual Taxonomy
A visual representation of the major architectural patterns and their relationships can be conceptualized as follows:
```markdown
graph LR
    A[Centralized] -->|employs|> B[Hierarchical]
    A --> C[Supervisor-Worker]
    D[Decentralized] -->|employs|> E[Collaborative]
    D --> F[Swarm]
    G[Hybrid] -->|combines|> C
    G -->|combines|> F
    H[Graph Orchestration] -->|effective|> I[Production]
    J[Router] -->|classifies input|> K[Specialized Agents]
    L[Skills] -->|loads prompts|> M[On-demand Knowledge]
    N[Handoffs] -->|changes agent|> O[Conversation Context]
```
This graph illustrates the relationships between different architectural patterns and highlights the complexity of multi-agent LLM systems.

## Conclusion
The landscape of multi-agent LLM systems is characterized by diverse architectural patterns and significant open challenges. Understanding these patterns and their interrelations is crucial for advancing the field. Addressing the identified open problems will be key to developing more robust, scalable, and secure multi-agent systems.


---

## Detailed Citation Results
| # | Claim | Sources |
|---|---|---|
| c0 | The major architectural patterns in multi-agent LLM systems include centralized and decentralized architectures. | https://resources.anthropic.com/hubfs/Building%20Effective%20AI%20Agents-%20Architecture%20Patterns%20and%20Implementation%20Frameworks.pdf |
| c1 | Centralized systems employ hierarchical patterns where a central supervisor delegates tasks to specialized agents. | https://resources.anthropic.com/hubfs/Building%20Effective%20AI%20Agents-%20Architecture%20Patterns%20and%20Implementation%20Frameworks.pdf |
| c2 | Decentralized systems use collaborative patterns where autonomous agents communicate directly in a peer-to-peer fashion. | https://resources.anthropic.com/hubfs/Building%20Effective%20AI%20Agents-%20Architecture%20Patterns%20and%20Implementation%20Frameworks.pdf |
| c3 | Four architectural patterns form the foundation of most multi-agent applications: subagents, skills, handoffs, and routers. | https://www.langchain.com/blog/choosing-the-right-multi-agent-architecture |
| c4 | Network configurations in multi-agent systems include Supervisor, Swarm, Hierarchical, and Single Information Environment (SIE) architectures. | https://arxiv.org/pdf/2601.03328 |
| c5 | Five primary communication architectures in LLM-based multi-agent systems are Flat, Hierarchical, Team, Society, and Hybrid architectures. | https://arxiv.org/html/2502.14321 |
| c6 | Topological patterns for multi-agent LLM systems include Chain, Route, Parallel, Orchestrate, Loop, and Hierarchy structures. | https://arxiv.org/html/2605.13850v2 |
| c7 | The major architectural patterns in multi-agent LLM systems include supervisor-worker, hierarchical, swarm, and graph orchestration. | https://www.digitalapplied.com/blog/agent-architecture-patterns-taxonomy-2026, https://www.paiteq.com/blog/multi-agent-orchestration-patterns/ |
| c8 | Supervisor-worker and hierarchical patterns are related in that they both involve a level of supervision or orchestration. | https://arxiv.org/pdf/2601.03328, https://www.paiteq.com/blog/multi-agent-orchestration-patterns/ |
| c9 | Swarm and blackboard patterns are theoretically interesting but rarely outperform hierarchical or graph patterns in practice. | https://www.digitalapplied.com/blog/agent-architecture-patterns-taxonomy-2026 |
| c10 | Graph orchestration and hierarchical patterns are considered effective in production environments. | https://www.digitalapplied.com/blog/agent-architecture-patterns-taxonomy-2026 |
| c11 | The router pattern involves a routing step that classifies input and directs it to specialized agents, executing queries in parallel and synthesizing results. | https://www.langchain.com/blog/choosing-the-right-multi-agent-architecture |
| c12 | The skills pattern involves a single agent loading specialized prompts and knowledge on-demand. | https://www.langchain.com/blog/choosing-the-right-multi-agent-architecture |
| c13 | The handoffs pattern involves the active agent changing dynamically based on conversation context. | https://www.langchain.com/blog/choosing-the-right-multi-agent-architecture |
| c14 | Most production agent systems are compositions of two or three canonical patterns. | https://www.digitalapplied.com/blog/agent-architecture-patterns-taxonomy-2026 |
| c15 | Hybrid patterns, such as supervisor-plus-pipeline and supervisor-plus-swarm, are common in production systems. | https://www.paiteq.com/blog/multi-agent-orchestration-patterns/ |
| c16 | Managing memory in multi-agent systems is fraught with challenges and open problems, especially in the realms of safety, security, and privacy. | https://arxiv.org/abs/2402.03578 |
| c17 | Implementing robust access control mechanisms is crucial to ensure sensitive information of an agent is not accessible to all agents. | https://arxiv.org/abs/2402.03578 |
| c18 | Ensuring the integrity of shared knowledge is critical to ensure the correct execution of tasks in multi-agent systems. | https://arxiv.org/abs/2402.03578 |
| c19 | Determining how to effectively recall and utilize contextually relevant past interactions among agents for current problem-solving scenarios is an open problem. | https://arxiv.org/abs/2402.03578 |
| c20 | Scalability, security, and multimodal integration are open issues in multi-agent LLM systems. | https://arxiv.org/html/2502.14321 |
| c21 | Functional redundancy among different communication protocols can lead to unnecessary complexity, resource wastage, and increased difficulty in protocol management. | https://arxiv.org/html/2502.14321 |
| c22 | Interoperability, multimodal integration, and security are key challenges in multi-agent LLM systems. | https://arxiv.org/html/2502.14321 |
| c23 | Detecting and mitigating hallucinations in multi-agent LLM systems is a crucial task and presents a unique set of challenges. | https://arxiv.org/html/2402.01680 |
| c24 | The number of agents in a multi-agent LLM system poses a significant challenge from a computational complexity perspective. | https://arxiv.org/html/2402.01680 |
| c25 | Steerability as an RL target is a named open problem. | https://arxiv.org/html/2605.02801 |
| c26 | Identifying the optimal macro-level communication pattern among agents that maximizes task performance while minimizing unnecessary communication overhead is an open problem. | https://arxiv.org/html/2505.22467v1 |
| c27 | Automatically profiling and selecting an effective structure for agents rather than relying on ad-hoc human design is a critical open problem. | https://arxiv.org/html/2505.22467v1 |
| c28 | Pruning unnecessary links while preserving task performance is an open problem. | https://arxiv.org/html/2505.22467v1 |
| c29 | Designing the micro-structure while considering the specific role of each agent to maximize performance is an open problem. | https://arxiv.org/html/2505.22467v1 |

## Sources
- [https://arxiv.org/pdf/2601.03328] LLM-Enabled Multi-Agent Systems: Empirical Evaluation and Insights into Emerging Design Patterns & Paradigms
- [https://resources.anthropic.com/hubfs/Building%20Effective%20AI%20Agents-%20Architecture%20Patterns%20and%20Implementation%20Frameworks.pdf] Building Effective AI Agents: Architecture Patterns and Implementation Frameworks
- [https://www.langchain.com/blog/choosing-the-right-multi-agent-architecture] Choosing the Right Multi-Agent Architecture
- [https://arxiv.org/html/2502.14321] Beyond Self-Talk: A Communication-Centric Survey of LLM-Based Multi-Agent Systems
- [https://arxiv.org/html/2605.13850v2] A Two-Dimensional Framework for AI Agent Design Patterns: Cognitive Function × Execution Topology
- [https://www.paiteq.com/blog/multi-agent-orchestration-patterns/] Multi-agent system orchestration patterns | Paiteq
- [https://bayesianpersuasion.com/posts/architectural-primitives-multi-agent-frameworks] Architectural Primitives of Multi-Agent Orchestration Frameworks
- [https://www.digitalapplied.com/blog/agent-architecture-patterns-taxonomy-2026] Agent Architecture Patterns: 2026 Taxonomy Guide
- [https://arxiv.org/abs/2402.03578] LLM Multi-Agent Systems: Challenges and Open Problems
- [https://arxiv.org/html/2402.01680] Large Language Model based Multi-Agents: A Survey of Progress and Challenges
- [https://arxiv.org/html/2605.02801] Reinforcement Learning for LLM-based Multi-Agent Systems through Orchestration Traces
- [https://arxiv.org/html/2505.22467v1] Topological Structure Learning Should Be A Research Priority for LLM-Based Multi-Agent Systems