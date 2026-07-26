/**
 * AI Assistant Component
 * Provides intelligent terrain analysis and recommendations
 */

import { useState } from 'react';
import { Brain, Sparkles, AlertCircle, CheckCircle, Loader } from 'lucide-react';
import type { BoundingBox } from '@/types';
import { calculateArea } from '@/types';

interface TerrainAnalysis {
  terrain_type: string;
  vegetation_type: string;
  elevation_range: {
    min: number;
    max: number;
  };
  recommended_resolution: number;
  recommended_features: string[];
  quality_prediction: number;
  confidence: number;
  analysis_text: string;
  warnings: string[];
}

interface AIAssistantProps {
  bbox: BoundingBox | null;
  onApplyRecommendations?: (settings: Record<string, unknown>) => void;
}

const AIAssistant: React.FC<AIAssistantProps> = ({ bbox, onApplyRecommendations }) => {
  const [analysis, setAnalysis] = useState<TerrainAnalysis | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [aiAvailable, setAiAvailable] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const analyzeTerrain = async () => {
    if (!bbox) {
      setError('Please select an area on the map first');
      return;
    }

    setIsAnalyzing(true);
    setError(null);

    try {
      // Check AI availability
      const healthResponse = await fetch('/api/ai/health');
      const health = await healthResponse.json();
      setAiAvailable(health.ollama_available);

      // Request analysis
      const response = await fetch('/api/ai/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          bbox: {
            north: bbox.north,
            south: bbox.south,
            east: bbox.east,
            west: bbox.west,
          },
          elevation_data: {
            min: 0,
            max: 500,
            slope_avg: 10,
            slope_max: 45,
            area_km2: calculateArea(bbox),
          },
        }),
      });

      if (!response.ok) {
        throw new Error('Analysis failed');
      }

      const result = await response.json();
      setAnalysis(result);

    } catch (err) {
      console.error('AI analysis failed:', err);
      setError('Failed to analyze terrain. Using fallback analysis.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const applyRecommendations = async () => {
    if (!analysis || !onApplyRecommendations) return;

    // Fetch optimized settings
    try {
      const response = await fetch('/api/ai/optimize-settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          bbox,
          elevation_data: {},
        }),
      });

      const optimized = await response.json();
      onApplyRecommendations(optimized);

    } catch (err) {
      console.error('Failed to apply recommendations:', err);
    }
  };

  const getQualityColor = (score: number) => {
    if (score >= 0.8) return 'text-green-600 dark:text-green-400';
    if (score >= 0.6) return 'text-blue-600 dark:text-blue-400';
    if (score >= 0.4) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  };

  const getQualityLabel = (score: number) => {
    if (score >= 0.8) return 'Excellent';
    if (score >= 0.6) return 'Good';
    if (score >= 0.4) return 'Fair';
    return 'Limited';
  };

  return (
    <div className="glass rounded-lg p-6 shadow-lg">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <Brain className="w-6 h-6 text-purple-600 dark:text-purple-400" />
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              AI Terrain Assistant
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {aiAvailable ? 'Powered by Ollama' : 'Rule-based mode'}
            </p>
          </div>
        </div>
        <button
          onClick={analyzeTerrain}
          disabled={!bbox || isAnalyzing}
          className={`flex items-center space-x-2 px-4 py-2 rounded-md transition ${
            isAnalyzing
              ? 'bg-gray-300 dark:bg-gray-600 cursor-not-allowed'
              : 'bg-purple-600 hover:bg-purple-700 text-white'
          }`}
        >
          {isAnalyzing ? (
            <Loader className="w-4 h-4 animate-spin" />
          ) : (
            <Sparkles className="w-4 h-4" />
          )}
          <span>{isAnalyzing ? 'Analyzing...' : 'Analyze'}</span>
        </button>
      </div>

      {/* Error State */}
      {error && (
        <div className="mb-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-md flex items-start space-x-2">
          <AlertCircle className="w-5 h-5 text-yellow-600 dark:text-yellow-400 mt-0.5" />
          <p className="text-sm text-yellow-800 dark:text-yellow-200">{error}</p>
        </div>
      )}

      {/* Empty State */}
      {!analysis && !isAnalyzing && !error && (
        <div className="text-center py-8 text-gray-500 dark:text-gray-400">
          <Brain className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="mb-2">Select an area and click Analyze</p>
          <p className="text-xs">
            Get AI-powered recommendations for optimal terrain generation
          </p>
        </div>
      )}

      {/* Analysis Results */}
      {analysis && (
        <div className="space-y-4">
          {/* Terrain Type */}
          <div className="p-4 bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20 rounded-lg border border-purple-200 dark:border-purple-800">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Terrain Type</p>
                <p className="font-semibold text-gray-900 dark:text-white capitalize">
                  {analysis.terrain_type.replace('_', ' ')}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Vegetation</p>
                <p className="font-semibold text-gray-900 dark:text-white capitalize">
                  {analysis.vegetation_type.replace('_', ' ')}
                </p>
              </div>
            </div>
          </div>

          {/* Quality Prediction */}
          <div className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600 dark:text-gray-400">Expected Quality</span>
              <span className={`text-lg font-bold ${getQualityColor(analysis.quality_prediction)}`}>
                {getQualityLabel(analysis.quality_prediction)}
              </span>
            </div>
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
              <div
                className="bg-gradient-to-r from-purple-600 to-blue-600 h-2 rounded-full transition-all duration-500"
                style={{ width: `${analysis.quality_prediction * 100}%` }}
              />
            </div>
            <div className="mt-2 flex justify-between text-xs text-gray-500 dark:text-gray-400">
              <span>Score: {(analysis.quality_prediction * 10).toFixed(1)}/10</span>
              <span>Confidence: {(analysis.confidence * 100).toFixed(0)}%</span>
            </div>
          </div>

          {/* Recommendations */}
          <div className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
            <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center">
              <CheckCircle className="w-4 h-4 mr-2 text-green-600" />
              Recommendations
            </h4>

            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Resolution:</span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {analysis.recommended_resolution}
                </span>
              </div>

              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Elevation Range:</span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {analysis.elevation_range.min.toFixed(0)}m - {analysis.elevation_range.max.toFixed(0)}m
                </span>
              </div>

              <div>
                <span className="text-gray-600 dark:text-gray-400 block mb-1">Features:</span>
                <div className="flex flex-wrap gap-2">
                  {analysis.recommended_features.map((feature) => (
                    <span
                      key={feature}
                      className="px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 text-xs rounded-full"
                    >
                      {feature}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Analysis Text */}
          <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
            <p className="text-sm text-blue-900 dark:text-blue-100">
              {analysis.analysis_text}
            </p>
          </div>

          {/* Warnings */}
          {analysis.warnings.length > 0 && (
            <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
              <h4 className="text-sm font-semibold text-yellow-900 dark:text-yellow-100 mb-2 flex items-center">
                <AlertCircle className="w-4 h-4 mr-2" />
                Notes
              </h4>
              <ul className="space-y-1">
                {analysis.warnings.map((warning, idx) => (
                  <li key={idx} className="text-xs text-yellow-800 dark:text-yellow-200">
                    • {warning}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Apply Button */}
          {onApplyRecommendations && (
            <button
              onClick={applyRecommendations}
              className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-md hover:from-purple-700 hover:to-blue-700 transition"
            >
              <Sparkles className="w-4 h-4" />
              <span>Apply AI Recommendations</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default AIAssistant;

