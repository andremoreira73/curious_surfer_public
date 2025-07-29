Here's a concise README for your demo repository:

# Curious Internet Surfer - AI Agent Job Search Demo

## Overview

This repository contains an experimental AI-powered web scraping system built to explore "vibe coding" (AI-assisted development using Claude Sonnet 3.7). The system searches corporate websites for interim manager positions using a multi-agent architecture.

**⚠️ Note: This was an experimental project to test AI-assisted coding capabilities. While functional, the implementation proved overly complex. The project has since been reimplemented using LangGraph - see [IM_Scanner in the lyfx_agents repo](https://github.com/andremoreira73/lyfx_agents) for the production version.**

## What This Demonstrates

- **Multi-Agent Architecture**: Coordinator, Explorer, Navigator, and Evaluator agents working together
- **Adaptive Learning**: Memory system that learns from previous searches to improve efficiency
- **Smart Content Processing**: Handles large pages through chunking and selective evaluation
- **Cost-Aware AI Usage**: Different models (GPT-4o-mini, GPT-4o, o3-mini) for different complexity tasks
- **Domain Configuration**: YAML-based configuration for easy adaptation to different search domains

## Architecture

```
├── Agent_modules/          # Core agent implementations
│   ├── Coordinator.py      # Orchestrates the entire workflow
│   ├── Explorer.py         # Decides which sites to visit (exploration vs exploitation)
│   ├── Navigator.py        # Analyzes website structure
│   ├── Evaluator.py        # Evaluates job listings for relevance
│   └── AgentMemory.py      # Persistent learning across runs
├── config.yaml             # Domain-specific configuration  (need target sites, refactored prompts for specific use case)
├── curious_surfer.py       # Main entry point
└── agent_memory.json       # Persisted learning data
```

## Key Features

- **Curious Browsing**: Explores sites organically rather than exhaustively scanning
- **Memory System**: Remembers successful patterns and site structures
- **Bilingual Support**: Handles both English and German job listings
- **Smart Filtering**: Pre-filters obviously irrelevant positions to save API costs
- **Detailed Reporting**: Generates HTML reports with findings

## Why This Exists

This project was an experiment in AI-assisted development to see how complex a system could be built primarily through AI code generation. The results:

- ✅ **Success**: The system is slow but works; it successfully finds relevant job listings
- ❌ **Over-Engineering**: The final implementation is significantly more complex than necessary
- 💡 **Learning**: Led to adopting LangGraph for a cleaner, more maintainable solution

## Running the Demo

```bash
# Install dependencies
conda env create -f environment.yml
conda activate spdr_env

# Run with default settings
python curious_surfer.py

# Or with custom parameters
python curious_surfer.py --max-visits 10 --satisfaction-threshold 5
```

## Configuration

Edit `config.yaml` to adapt the system for different domains:

- Target websites
- Search terminology (supports multiple languages)
- Evaluation criteria
- AI model selection

## Lessons Learned

1. **AI-generated code tends toward over-complexity** - What could be simple often becomes elaborate
2. **Framework selection matters** - LangGraph provides better abstractions for this use case
3. **Iterative refinement is key** - This experimental version informed a much cleaner implementation

## See Also

- **[IM_Scanner](https://github.com/andremoreira73/lyfx_agents)** - The production LangGraph-based version
- Built as an experiment in vibe coding with Claude
- Part of ongoing research into AI-assisted development patterns

## License

Proprietary - lyfX.ai

This repository is only made public to showcase our capabilities. If you wish to discuss licensing models, please contact us at
info@lyfx.ai or the author directly.

## Support

None. This repository is maintained for educational purposes to demonstrate AI-assisted development patterns and multi-agent architectures.

## Author

- Andre Moreira
- a.moreira@lyfx.ai
