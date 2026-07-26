package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	goruntime "runtime"
	"strings"
	"time"

	"clearflow/engine"
	"clearflow/engine/providers"
	"github.com/wailsapp/wails/v2/pkg/runtime"
)

type App struct {
	ctx     context.Context
	manager *providers.ProviderManager
	settings Settings
}

func NewApp() *App {
	return &App{
		settings: loadSettings(),
	}
}

func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
	
	paths, err := engine.ExtractAssets()
	if err != nil {
		runtime.MessageDialog(ctx, runtime.MessageDialogOptions{
			Type:    runtime.ErrorDialog,
			Title:   "Asset Error",
			Message: "Failed to extract core components: " + err.Error(),
		})
		return
	}

	a.manager = providers.NewProviderManager()
	
	// Register platform-specific providers
	if goruntime.GOOS == "windows" {
		a.manager.Register(providers.NewZapret2WindowsProvider(paths.BinDir, paths.LuaDir))
		a.manager.Register(providers.NewGoodbyeDPIProvider(paths.BinDir))
	} else if goruntime.GOOS == "linux" {
		a.manager.Register(providers.NewZapretLinuxProvider(paths.BinDir))
	} else if goruntime.GOOS == "darwin" {
		a.manager.Register(providers.NewZapretMacOSProvider(paths.BinDir))
	}
	
	isAdmin, _ := a.manager.CheckPrivileges()
	if !isAdmin {
		a.relaunchAsAdmin()
		return
	}

	for _, arg := range os.Args {
		if arg == "--autostart" {
			a.manager.Start(a.ctx, a.settings.EngineName, a.settings.ProfileName)
			break
		}
	}
}

func (a *App) LoadConfig() Settings {
	return a.settings
}

func (a *App) SaveConfig(engineName, profileName string) {
	a.settings.EngineName = engineName
	a.settings.ProfileName = profileName
	saveSettings(a.settings)
}

type ScanResult struct {
	Success     bool   `json:"success"`
	EngineName  string `json:"engineName"`
	ProfileName string `json:"profileName"`
}

func (a *App) AutoScan() ScanResult {
	targets := []string{"https://discord.com", "https://www.youtube.com"}
	
	engines := a.manager.GetEngineNames()
	for _, engineName := range engines {
		profiles := a.manager.GetProfiles(engineName)
		for _, profile := range profiles {
			runtime.EventsEmit(a.ctx, "scan_log", fmt.Sprintf("Testing: %s -> %s", engineName, profile))
			
			a.manager.Stop()
			// Wait for old processes to die completely
			time.Sleep(1 * time.Second)
			
			a.manager.Start(a.ctx, engineName, profile)
			time.Sleep(3 * time.Second) // wait for WinDivert hook

			success := true
			for _, target := range targets {
				if !a.checkConnectivity(target) {
					success = false
					break
				}
			}

			if success {
				runtime.EventsEmit(a.ctx, "scan_log", "Optimal configuration found!")
				a.SaveConfig(engineName, profile)
				return ScanResult{Success: true, EngineName: engineName, ProfileName: profile}
			}
		}
	}
	
	a.manager.Stop()
	return ScanResult{Success: false}
}

func (a *App) checkConnectivity(url string) bool {
	client := &http.Client{
		Timeout: 4 * time.Second,
		Transport: &http.Transport{
			Proxy: nil,
			DisableKeepAlives: true,
		},
	}
	resp, err := client.Get(url)
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	return resp.StatusCode == http.StatusOK
}

func (a *App) CheckAutostart() bool {
	return a.settings.Autostart
}

func (a *App) ToggleAutostart(enable bool) string {
	a.settings.Autostart = enable
	saveSettings(a.settings)

	exePath, err := os.Executable()
	if err != nil {
		return "Error finding executable path"
	}

	if enable {
		cmdStr := fmt.Sprintf(`schtasks /create /tn "UnboundDPI" /tr "\"%s\" --autostart" /sc onlogon /rl highest /f`, exePath)
		cmd := exec.Command("cmd", "/c", cmdStr)
		if err := cmd.Run(); err != nil {
			return "Error enabling autostart: " + err.Error()
		}
		return "Autostart Enabled"
	} else {
		cmd := exec.Command("schtasks", "/delete", "/tn", "UnboundDPI", "/f")
		if err := cmd.Run(); err != nil {
			return "Error disabling autostart: " + err.Error()
		}
		return "Autostart Disabled"
	}
}

func (a *App) relaunchAsAdmin() {
	exe, _ := os.Executable()
	cwd, _ := os.Getwd()
	args := strings.Join(os.Args[1:], " ")

	verb := "runas"
	cmd := exec.Command("powershell", "Start-Process", fmt.Sprintf("'%s'", exe), "-ArgumentList", fmt.Sprintf("'%s'", args), "-WorkingDirectory", fmt.Sprintf("'%s'", cwd), "-Verb", verb)
	cmd.Start()
	os.Exit(0)
}

func (a *App) ToggleEngine(active bool, engineName string, profile string) string {
	if active {
		err := a.manager.Start(a.ctx, engineName, profile)
		if err != nil {
			return "Error: " + err.Error()
		}
		return "Started"
	} else {
		a.manager.Stop()
		return "Stopped"
	}
}

func (a *App) GetEngines() []string {
	if a.manager == nil {
		return []string{}
	}
	return a.manager.GetEngineNames()
}

func (a *App) GetProfiles(engineName string) []string {
	if a.manager == nil {
		return []string{}
	}
	return a.manager.GetProfiles(engineName)
}

func (a *App) GetStatus() providers.Status {
	if a.manager == nil {
		return providers.StatusStopped
	}
	return a.manager.GetStatus()
}

func (a *App) GetLogs() []string {
	if a.manager == nil {
		return []string{}
	}
	return a.manager.GetLogs()
}

func (a *App) onBeforeClose(ctx context.Context) bool {
	if a.manager != nil {
		a.manager.Stop()
	}
	return false
}
