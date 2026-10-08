import pytest
from app.presets.demo_towers import get_demo_tower
from app.engine.analysis_service import TowerAnalysisService
from app.engine.optimizer import TowerOptimizer

def test_optimizer_ranks_and_recommends_safe_design():
    t40 = get_demo_tower("40m")
    baseline = TowerAnalysisService.analyze(t40)
    optimizer = TowerOptimizer(t40)
    response = optimizer.run_optimization(baseline)
    
    assert len(response.candidates) >= 5
    assert response.recommended_configuration is not None
    assert response.recommended_configuration.is_recommended is True
    # The recommended configuration must be within acceptable structural utilization limits
    assert response.recommended_configuration.max_utilization <= 1.05
    assert response.tradeoff_summary != ""
