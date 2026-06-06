# GSD Workflow Configuration

agents = {
    "danielle": {
        "name": "Danielle",
        "role": "Developer",
        "model": "Qwen3 Coder",
        "primary_focus": [
            "Jurisdiction mapping",
            "Form-to-jurisdiction mapping",
            "Business logic implementation",
            "Federal/local rule changes"
        ],
        "evidence_standards": [
            "Code commits",
            "Test coverage reports",
            "Documentation updates"
        ]
    },
    "pete": {
        "name": "Pete",
        "role": "Product Manager",
        "model": "Kimi K2.6",
        "primary_focus": [
            "Court announcements",
            "Federal publications",
            "Local rule changes",
            "US Trustee updates"
        ],
        "requirements_priorities": [
            "Requirements analysis",
            "Business impact assessment",
            "Implementation planning",
            "Acceptance criteria creation"
        ],
        "evidence_standards": [
            "Requirements documents",
            "Impact assessments",
            "Implementation plans"
        ]
    },
    "randy": {
        "name": "Randy",
        "role": "Hostile Reviewer",
        "model": "Nemotron 3 Super",
        "primary_focus": [
            "Assumption testing",
            "Failure mode analysis",
            "Risk assessment",
            "Threat analysis"
        ],
        "evidence_standards": [
            "Risk assessment reports",
            "Edge case documentation",
            "Challenge reports"
        ]
    },
    "vern": {
        "name": "Vern",
        "role": "Validation Agent",
        "models": ["DeepSeek V4 Flash", "Qwen3 Coder"],
        "primary_focus": [
            "Comprehensive testing",
            "End-to-end validation",
            "Integration testing",
            "Unit testing"
        ],
        "validation_priorities": [
            "Test planning",
            "Acceptance testing",
            "Regression testing",
            "Coverage testing"
        ],
        "evidence_standards": [
            "Test plans",
            "Validation reports",
            "Coverage metrics"
        ]
    }
}

# Workflow process
workflow = {
    "evidence_standards": {
        "priority": "highest",
        "description": "Agents must automatically generate execution logs, link to passing test coverage, and provide state-change artifacts"
    },
    "interaction_protocols": {
        "priority": "high",
        "description": "Establish rigid boundaries for agent interactions and define communication protocols"
    },
    "review_process": {
        "priority": "moderate",
        "description": "Shift to post-execution automated audits using static analysis and integration tests"
    },
    "approval_requirements": {
        "priority": "minimized",
        "description": "Eliminate approvals for routine tasks, reserve strict human approval only for high-stakes actions"
    }
}

# Agent interaction flow
interaction_flow = [
    "Pete analyzes announcements and source documents",
    "Danielle implements based on Pete's requirements",
    "Randy performs hostile review of implementation",
    "Danielle addresses Randy's feedback",
    "Vern validates the implementation",
    "Human approval for high-stakes changes"
]