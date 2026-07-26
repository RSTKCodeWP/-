import { useState } from 'react';
import { Loader, Brain, AlertCircle, CheckCircle } from 'lucide-react';

interface AISettings {
  enabled: boolean;
  ollama_url: string;
  vision_model: string;
  coder_model: string;
  auto_analyze: boolean;
  timeout_seconds: number;
}

interface AITabProps {
  settings: AISettings;
  onSave: (settings: AISettings) => void;
  saving: boolean;
}

const AITab: React.FC<AITabProps> = ({ settings, onSave, saving }) => {
  const defaultSettings: AISettings = {
    enabled: false,
    ollama_url: 'http://localhost:11434',
    vision_model: 'qwen3-vl:235b-cloud',
    coder_model: 'qwen3-coder:480b-cloud',
    auto_analyze: false,
    timeout_seconds: 120,
  };

  const [formData, setFormData] = useState<AISettings>({
    ...defaultSettings,
    ...settings,
  });

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);

    try {
      const response = await fetch('/api/ai/health');
      const health = await response.json();

      if (health.ollama_available) {
        setTestResult({
          success: true,
          message: `Ollama подключен. Модели: ${health.vision_available ? '✅ Vision' : '❌ Vision'}, ${health.coder_available ? '✅ Coder' : '❌ Coder'}`
        });
      } else {
        setTestResult({
          success: false,
          message: 'Ollama недоступен. Проверьте что сервер запущен.'
        });
      }
    } catch (error) {
      setTestResult({
        success: false,
        message: 'Ошибка подключения к Ollama'
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xl font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Brain className="w-6 h-6 text-purple-600" />
            AI Ассистент (Qwen3)
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Умный анализ местности и генерация конфигураций
          </p>
        </div>
        <label className="flex items-center">
          <input
            type="checkbox"
            checked={formData.enabled}
            onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
            className="rounded text-blue-600"
          />
          <span className="ml-2 text-sm font-medium text-gray-700 dark:text-gray-300">
            Включить AI
          </span>
        </label>
      </div>

      {formData.enabled && (
        <>
          {/* Ollama URL */}
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700 space-y-4">
            <h4 className="font-semibold text-gray-900 dark:text-white">Ollama Server</h4>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Ollama URL
              </label>
              <input
                type="text"
                value={formData.ollama_url}
                onChange={(e) => setFormData({ ...formData, ollama_url: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                placeholder="http://localhost:11434"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Адрес локального или удаленного Ollama сервера
              </p>
            </div>

            <button
              onClick={handleTest}
              disabled={testing}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {testing ? (
                <>
                  <Loader className="w-4 h-4 animate-spin" />
                  <span>Проверка...</span>
                </>
              ) : (
                <>
                  <CheckCircle className="w-4 h-4" />
                  <span>Проверить подключение</span>
                </>
              )}
            </button>

            {testResult && (
              <div className={`flex items-center gap-2 p-3 rounded-md ${
                testResult.success 
                  ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300' 
                  : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300'
              }`}>
                {testResult.success ? (
                  <CheckCircle className="w-5 h-5" />
                ) : (
                  <AlertCircle className="w-5 h-5" />
                )}
                <span className="text-sm">{testResult.message}</span>
              </div>
            )}
          </div>

          {/* Models */}
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700 space-y-4">
            <h4 className="font-semibold text-gray-900 dark:text-white">Модели (Cloud)</h4>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Vision Model (анализ изображений)
              </label>
              <input
                type="text"
                value={formData.vision_model}
                onChange={(e) => setFormData({ ...formData, vision_model: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Рекомендуется: qwen3-vl:235b-cloud
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Coder Model (генерация конфигураций)
              </label>
              <input
                type="text"
                value={formData.coder_model}
                onChange={(e) => setFormData({ ...formData, coder_model: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Рекомендуется: qwen3-coder:480b-cloud
              </p>
            </div>
          </div>

          {/* Options */}
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700 space-y-4">
            <h4 className="font-semibold text-gray-900 dark:text-white">Опции</h4>
            
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={formData.auto_analyze}
                onChange={(e) => setFormData({ ...formData, auto_analyze: e.target.checked })}
                className="rounded text-blue-600"
              />
              <span className="ml-2 text-sm text-gray-700 dark:text-gray-300">
                Автоматически анализировать при выборе области
              </span>
            </label>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Timeout (секунды)
              </label>
              <input
                type="number"
                min="30"
                max="300"
                value={formData.timeout_seconds}
                onChange={(e) => setFormData({ ...formData, timeout_seconds: Number(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Максимальное время ожидания ответа от AI
              </p>
            </div>
          </div>

          {/* Info */}
          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <div className="flex gap-3">
              <AlertCircle className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-blue-800 dark:text-blue-200">
                <p className="font-medium mb-2">Установка моделей:</p>
                <code className="block bg-white dark:bg-gray-900 p-2 rounded text-xs mb-1">
                  ollama pull qwen3-vl:235b-cloud
                </code>
                <code className="block bg-white dark:bg-gray-900 p-2 rounded text-xs">
                  ollama pull qwen3-coder:480b-cloud
                </code>
                <p className="mt-2 text-xs">
                  Cloud модели работают через Ollama Cloud API и не требуют локальной загрузки.
                </p>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Save Button */}
      <div className="flex justify-end pt-6 border-t border-gray-200 dark:border-gray-700">
        <button
          onClick={() => onSave(formData)}
          disabled={saving}
          className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
        >
          {saving && <Loader className="w-4 h-4 animate-spin" />}
          <span>Сохранить настройки AI</span>
        </button>
      </div>
    </div>
  );
};

export default AITab;
