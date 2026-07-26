package main

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type Settings struct {
	EngineName  string `json:"engineName"`
	ProfileName string `json:"profileName"`
	Autostart   bool   `json:"autostart"`
}

func getSettingsPath() string {
	configDir, err := os.UserConfigDir()
	if err != nil {
		configDir = os.TempDir()
	}
	appDir := filepath.Join(configDir, "Unbound")
	os.MkdirAll(appDir, 0755)
	return filepath.Join(appDir, "settings.json")
}

func loadSettings() Settings {
	var s Settings
	// Set defaults
	s.EngineName = "Zapret 2 (winws)"
	s.ProfileName = "Unbound Ultimate (God Mode)"
	s.Autostart = false

	data, err := os.ReadFile(getSettingsPath())
	if err == nil {
		json.Unmarshal(data, &s)
	}
	return s
}

func saveSettings(s Settings) error {
	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(getSettingsPath(), data, 0644)
}
