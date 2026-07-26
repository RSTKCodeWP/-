"""
AI-Powered Terrain Analyzer
Uses Ollama for intelligent terrain analysis and recommendations
"""

import json
import logging
from enum import Enum
from typing import Any, Dict, List

import httpx
from pydantic import BaseModel

from ..config import settings

logger = logging.getLogger(__name__)


class TerrainType(str, Enum):
    """Types of terrain"""
    MOUNTAIN = "mountain"
    VALLEY = "valley"
    PLATEAU = "plateau"
    PLAINS = "plains"
    COASTAL = "coastal"
    DESERT = "desert"
    URBAN = "urban"
    FOREST = "forest"
    MIXED = "mixed"


class VegetationType(str, Enum):
    """Types of vegetation"""
    DENSE_FOREST = "dense_forest"
    SPARSE_FOREST = "sparse_forest"
    GRASSLAND = "grassland"
    SHRUBLAND = "shrubland"
    DESERT = "desert"
    TUNDRA = "tundra"
    URBAN = "urban"
    MIXED = "mixed"


class TerrainAnalysis(BaseModel):
    """Result of terrain analysis"""
    terrain_type: TerrainType
    vegetation_type: VegetationType
    elevation_range: Dict[str, float]
    slope_characteristics: Dict[str, Any]
    recommended_resolution: int
    recommended_features: List[str]
    quality_prediction: float  # 0-1 score
    confidence: float  # 0-1 score
    analysis_text: str
    warnings: List[str] = []


class Recommendations(BaseModel):
    """AI-generated recommendations for terrain generation"""
    suggested_resolution: int
    suggested_sources: List[str]
    suggested_features: Dict[str, bool]
    quality_prediction: float
    confidence_score: float
    reasoning: str
    tips: List[str]


class TerrainAnalyzer:
    """
    Analyzes terrain using AI to provide intelligent recommendations
    """

    def __init__(self, ollama_host: str = "http://localhost:11434"):
        """
        Initialize the terrain analyzer

        Args:
            ollama_host: Ollama API endpoint
        """
        self.ollama_host = ollama_host
        self.model = getattr(settings, 'ollama_vision_model', 'llama3.1:8b')
        self.timeout = 30.0

    async def check_ollama_available(self) -> bool:
        """Check if Ollama is available"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.ollama_host}/api/tags",
                    timeout=5.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return False

    async def analyze_terrain_type(
        self,
        elevation_data: Dict[str, Any],
        bbox: Dict[str, float]
    ) -> TerrainAnalysis:
        """
        Analyze terrain type using AI

        Args:
            elevation_data: Dictionary with elevation statistics
            bbox: Bounding box coordinates

        Returns:
            Terrain analysis result
        """
        # Check if Ollama is available
        if not await self.check_ollama_available():
            logger.info("Ollama not available, using rule-based analysis")
            return self._rule_based_analysis(elevation_data, bbox)

        # Prepare analysis prompt
        prompt = self._create_analysis_prompt(elevation_data, bbox)

        try:
            # Call Ollama API
            analysis_text = await self._call_ollama(prompt)

            # Parse AI response
            return self._parse_ai_analysis(analysis_text, elevation_data)

        except Exception as e:
            logger.error(f"AI analysis failed: {e}, falling back to rules")
            return self._rule_based_analysis(elevation_data, bbox)

    def _create_analysis_prompt(
        self,
        elevation_data: Dict[str, Any],
        bbox: Dict[str, float]
    ) -> str:
        """Create analysis prompt for AI"""

        elev_min = elevation_data.get('min', 0)
        elev_max = elevation_data.get('max', 0)
        elev_range = elev_max - elev_min

        slope_avg = elevation_data.get('slope_avg', 0)
        slope_max = elevation_data.get('slope_max', 0)

        area_km2 = elevation_data.get('area_km2', 0)

        prompt = f"""Analyze this terrain data and provide recommendations:

Location: {bbox.get('north', 0):.4f}°N, {bbox.get('west', 0):.4f}°W

Elevation:
- Range: {elev_min:.1f}m to {elev_max:.1f}m
- Difference: {elev_range:.1f}m

Slope:
- Average: {slope_avg:.1f}°
- Maximum: {slope_max:.1f}°

Area: {area_km2:.2f} km²

Based on this data, determine:
1. Terrain type (mountain, valley, plateau, plains, coastal, desert, urban, forest, mixed)
2. Likely vegetation type (dense_forest, sparse_forest, grassland, shrubland, desert, tundra, urban, mixed)
3. Recommended heightmap resolution (1009, 2048, 4096)
4. Recommended features to enable (roads, buildings, vegetation, water_bodies)
5. Expected quality score (0-10)
6. Confidence in analysis (0-10)

Respond in JSON format:
{{
  "terrain_type": "...",
  "vegetation_type": "...",
  "recommended_resolution": 2048,
  "recommended_features": ["roads", "buildings"],
  "quality_score": 8,
  "confidence": 9,
  "reasoning": "Brief explanation..."
}}"""

        return prompt

    async def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,  # Lower for more consistent results
                    }
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            return data.get('response', '')

    def _parse_ai_analysis(
        self,
        ai_response: str,
        elevation_data: Dict[str, Any]
    ) -> TerrainAnalysis:
        """Parse AI response into TerrainAnalysis"""

        try:
            # Extract JSON from response
            json_start = ai_response.find('{')
            json_end = ai_response.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = ai_response[json_start:json_end]
                parsed = json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")

            # Map to TerrainAnalysis
            return TerrainAnalysis(
                terrain_type=TerrainType(parsed.get('terrain_type', 'mixed')),
                vegetation_type=VegetationType(parsed.get('vegetation_type', 'mixed')),
                elevation_range={
                    'min': elevation_data.get('min', 0),
                    'max': elevation_data.get('max', 0),
                },
                slope_characteristics={
                    'avg': elevation_data.get('slope_avg', 0),
                    'max': elevation_data.get('slope_max', 0),
                },
                recommended_resolution=parsed.get('recommended_resolution', 2048),
                recommended_features=parsed.get('recommended_features', []),
                quality_prediction=parsed.get('quality_score', 7) / 10.0,
                confidence=parsed.get('confidence', 7) / 10.0,
                analysis_text=parsed.get('reasoning', 'AI analysis completed'),
                warnings=[]
            )

        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}")
            # Fall back to rule-based
            return self._rule_based_analysis(elevation_data, {})

    def _rule_based_analysis(
        self,
        elevation_data: Dict[str, Any],
        bbox: Dict[str, float]
    ) -> TerrainAnalysis:
        """Fallback rule-based analysis when AI is not available"""

        elev_min = elevation_data.get('min', 0)
        elev_max = elevation_data.get('max', 0)
        elev_range = elev_max - elev_min
        slope_avg = elevation_data.get('slope_avg', 0)

        # Determine terrain type based on rules
        if elev_range > 1000 and slope_avg > 15:
            terrain_type = TerrainType.MOUNTAIN
            vegetation = VegetationType.SPARSE_FOREST
        elif elev_range > 500 and slope_avg > 10:
            terrain_type = TerrainType.VALLEY
            vegetation = VegetationType.DENSE_FOREST
        elif elev_min < 100 and elev_range < 200:
            terrain_type = TerrainType.COASTAL
            vegetation = VegetationType.GRASSLAND
        elif slope_avg < 5:
            terrain_type = TerrainType.PLAINS
            vegetation = VegetationType.GRASSLAND
        else:
            terrain_type = TerrainType.MIXED
            vegetation = VegetationType.MIXED

        # Determine resolution
        area_km2 = elevation_data.get('area_km2', 10)
        if area_km2 > 50:
            resolution = 4096
        elif area_km2 > 20:
            resolution = 2048
        else:
            resolution = 2048

        # Recommended features
        features = ['roads', 'vegetation', 'water_bodies']
        if terrain_type == TerrainType.URBAN or terrain_type == TerrainType.COASTAL:
            features.append('buildings')

        return TerrainAnalysis(
            terrain_type=terrain_type,
            vegetation_type=vegetation,
            elevation_range={'min': elev_min, 'max': elev_max},
            slope_characteristics={'avg': slope_avg, 'max': elevation_data.get('slope_max', 0)},
            recommended_resolution=resolution,
            recommended_features=features,
            quality_prediction=0.75,
            confidence=0.85,
            analysis_text=f"Rule-based analysis: {terrain_type.value} terrain with {vegetation.value}",
            warnings=["AI analysis not available, using rule-based fallback"]
        )

    async def get_recommendations(
        self,
        bbox: Dict[str, float],
        elevation_source: str = "auto"
    ) -> Recommendations:
        """
        Get AI-powered recommendations for terrain generation

        Args:
            bbox: Bounding box
            elevation_source: Preferred elevation source

        Returns:
            Recommendations object
        """
        # Mock elevation data (in real implementation, fetch from sources)
        elevation_data = {
            'min': 0,
            'max': 500,
            'slope_avg': 10,
            'slope_max': 45,
            'area_km2': 25
        }

        # Get terrain analysis
        analysis = await self.analyze_terrain_type(elevation_data, bbox)

        # Build recommendations
        return Recommendations(
            suggested_resolution=analysis.recommended_resolution,
            suggested_sources=['srtm', 'opentopography'] if analysis.terrain_type == TerrainType.MOUNTAIN else ['srtm'],
            suggested_features={
                'roads': 'roads' in analysis.recommended_features,
                'buildings': 'buildings' in analysis.recommended_features,
                'vegetation': 'vegetation' in analysis.recommended_features,
                'water_bodies': 'water_bodies' in analysis.recommended_features,
            },
            quality_prediction=analysis.quality_prediction,
            confidence_score=analysis.confidence,
            reasoning=analysis.analysis_text,
            tips=[
                f"This appears to be {analysis.terrain_type.value} terrain",
                f"Recommended resolution: {analysis.recommended_resolution}",
                f"Vegetation type: {analysis.vegetation_type.value}",
            ] + analysis.warnings
        )


# Global analyzer instance
terrain_analyzer = TerrainAnalyzer(
    ollama_host=getattr(settings, 'ollama_host', 'http://localhost:11434')
        )
