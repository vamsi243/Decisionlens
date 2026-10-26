# Decision Lens: project pitch

**Every moment, every option, every fan.**

| | |
| --- | --- |
| Live demo | https://orange-ocean-05183100f.5.azurestaticapps.net (free, no sign-in) |
| Demo video | _link coming soon_ |
| Code | https://github.com/vamsi243/Decisionlens |
| Category | **Best Multi-Agent System** (also fits Best Azure Cloud Native Integration) |

## The problem
Broadcasts tell you what happened, not what was possible. A fan sees a header lost at the back post. An analyst wants to know whether it was ever winnable, what the other options were, and whether a fresh substitute would have changed it. Today those answers take a video analyst hours after the final whistle, and they reach one audience in one language.

## What we built
A live match-intelligence board for a fully synthetic football match (*Riverside FC* v *Hillton United*, invented players). At every key moment it shows what happened, what was possible and who could have done it:

- the options the player had, drawn on the pitch with their chance of success;
- the best option against the chosen one;
- a what-if swap, such as "a fresh centre-back: 4% → 46%";
- one short line of explanation.

Every number comes from a transparent probability engine. The language model only writes the words around it, and a grounding guard rejects any text with a number the engine didn't produce. You can check the engine too: its pass probabilities land within 1.2 percentage points of what happened (calibration error 0.012), plotted on the board.

## The five stages
| Stage | Decision Lens |
| --- | --- |
| **Ingest** | Our own seeded match generator streams events (passes, shots, tackles, pressure, possession changes, subs) and 10 Hz tracking live through Azure Event Hubs |
| **Interpret** | Live stats, pass difficulty, ball and shot speed, distance, sprints, fatigue, and a five-minute intensity index that reads the game's rhythm: control, pressure or chaos |
| **Explain** | Option probabilities with ranges, what-if swaps and decision quality, explained by agents in two voices |
| **Render** | Time-coded cards on the board and downloadable overlay JSON, ready for a broadcast graphics engine |
| **Personalize** | Analyst and fan modes that are really different experiences, follow a player or a club, six languages, and a match copilot you can ask anything |

## Microsoft and Azure technology
- **Microsoft Agent Framework** agents on **Azure OpenAI in Microsoft Foundry**: mini, nano and fallback deployments at the lowest reasoning effort.
- A **Model Context Protocol** server (official MCP Python SDK) gives the agents the engine as tools.
- **AG-UI** (`agent-framework-ag-ui`) serves the match copilot to the chat on the board.
- **Azure AI Translator** handles the language switch.
- **Azure Container Apps**, **Event Hubs**, **SignalR Service**, **Cosmos DB**, **Static Web Apps**, **Key Vault**, **Container Registry** and **Application Insights** (OpenTelemetry), deployed with **azd + Bicep** under one managed identity, with no keys in code.

## Why several agents beat one
A rules router decides what runs, so frames and events never touch a model.

| Trigger | Agents that run |
| --- | --- |
| Key moment | **Moment** → **What-if** → **Narrator** |
| Half-time and full-time | **Interpreter** → **Recap** → **Decisions** |
| A viewer's question | **Copilot**, with engine tools |

- **Each agent has one small, grounded job.** The What-if agent picks the most instructive swap and calls the `what_if_swap` MCP tool. It never computes a number. The Narrator writes ≤ 25 words for analysts and ≤ 15 with no numbers for fans.
- **Shared state, not long prompts.** Agents hand off through a shared state store and the MCP tools, so each prompt stays short and cheap.
- **Failures stay local.** Each step has a cache, a timeout, a grounding check, one retry on a fallback model, and then an engine-built template. One bad answer never blanks a card or stalls the match.
- **The outcome no single agent could match:** a live, checked explanation of every key moment in two voices and six languages, at a handful of model calls per match.

## Who it's for
- **Broadcasters and studios:** overlay-ready, machine-readable cards in sync with the live clock.
- **Analysts:** options, ranges, drivers, workload and fatigue, live instead of hours later.
- **Fans in any market:** plain-language stories, their player and their club first, in their own language.

All data is synthetic. No real clubs, players, badges or footage.
