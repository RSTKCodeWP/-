"""
AI Analysis API Routes
Provides AI-powered terrain analysis and recommendations
"""

import logging
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..ai.terrain_analyzer import Recommendations, TerrainAnalysis, terrain_analyzer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["ai"])


class AnalyzeRequest(BaseModel):
    """Request for terrain analysis"""
    bbox: Dict[str, float]
    elevation_data: Optional[Dict] = None


class RecommendationsRequest(BaseModel):
    """Request for AI recommendations"""
    bbox: Dict[str, float]
    elevation_source: str = "auto"


@router.get("/health")
async def ai_health_check():
    """Check if AI features are available"""
    available = await terrain_analyzer.check_ollama_available()

    return {
        "ollama_available": available,
        "model": terrain_analyzer.model,
        "host": terrain_analyzer.ollama_host,
        "fallback_mode": "rule-based" if not available else None
    }


@router.post("/analyze", response_model=TerrainAnalysis)
async def analyze_terrain(request: AnalyzeRequest):
    """
    Analyze terrain using AI

    Args:
        request: Analysis request with bbox and optional elevation data

    Returns:
        Terrain analysis with recommendations
    """
    try:
        # Use provided elevation data or mock it
        elevation_data = request.elevation_data or {
            'min': 0,
            'max': 500,
            'slope_avg': 10,
            'slope_max': 45,
            'area_km2': 25
        }

        analysis = await terrain_analyzer.analyze_terrain_type(
            elevation_data,
            request.bbox
        )

        return analysis

    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        ) from e


@router.post("/recommendations", response_model=Recommendations)
async def get_recommendations(request: RecommendationsRequest):
    """
    Get AI-powered recommendations for terrain generation

    Args:
        request: Recommendations request with bbox

    Returns:
        Recommendations for optimal terrain generation
    """
    try:
        recommendations = await terrain_analyzer.get_recommendations(
            request.bbox,
            request.elevation_source
        )

        return recommendations

    except Exception as e:
        logger.error(f"Failed to get recommendations: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Recommendations failed: {str(e)}"
        ) from e


@router.get("/models")
async def list_ai_models():
    """List available AI models"""
    available = await terrain_analyzer.check_ollama_available()

    if not available:
        return {
            "available": False,
            "message": "Ollama not available"
        }

    # In a full implementation, query Ollama for available models
    return {
        "available": True,
        "current_model": terrain_analyzer.model,
        "recommended_models": [
            {
                "name": "llama3.1:8b",
                "description": "Balanced performance and speed",
                "size": "4.7GB"
            },
            {
                "name": "llama3.1:70b",
                "description": "Highest quality analysis",
                "size": "40GB"
            },
            {
                "name": "mixtral:8x7b",
                "description": "Fast multi-expert model",
                "size": "26GB"
            }
        ]
    }


@router.post("/optimize-settings")
async def optimize_generation_settings(request: AnalyzeRequest):
    """
    Optimize terrain generation settings based on AI analysis

    Args:
        request: Analysis request

    Returns:
        Optimized settings
    """
    try:
        analysis = await terrain_analyzer.analyze_terrain_type(
            request.elevation_data or {},
            request.bbox
        )

        # Build optimized settings
        optimized = {
            "resolution": analysis.recommended_resolution,
            "features": {
                "roads": "roads" in analysis.recommended_features,
                "buildings": "buildings" in analysis.recommended_features,
                "vegetation": "vegetation" in analysis.recommended_features,
                "water_bodies": "water_bodies" in analysis.recommended_features,
                "weightmaps": analysis.terrain_type.value in ["mountain", "forest"],
            },
            "elevation_source": "opentopography" if analysis.terrain_type.value == "mountain" else "auto",
            "export_formats": ["unreal5", "geotiff"],
            "terrain_analysis": {
                "type": analysis.terrain_type.value,
                "vegetation": analysis.vegetation_type.value,
                "quality_prediction": analysis.quality_prediction,
                "confidence": analysis.confidence,
            },
            "tips": [
                analysis.analysis_text,
                f"Predicted quality: {analysis.quality_prediction * 10:.1f}/10",
                f"Analysis confidence: {analysis.confidence * 100:.0f}%",
            ] + analysis.warnings
        }

        return optimized

    except Exception as e:
        logger.error(f"Settings optimization failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Optimization failed: {str(e)}"
        ) from e

