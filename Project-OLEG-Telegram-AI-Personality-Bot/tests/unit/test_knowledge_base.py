"""
Unit tests for Knowledge Base service.

**Feature: anti-hallucination-v1**
"""

import pytest
from app.services.knowledge_base import knowledge_base, GPUInfo


class TestKnowledgeBase:
    """Tests for KnowledgeBase class."""
    
    def test_get_nvidia_gpu(self):
        """Should return info for NVIDIA GPUs."""
        gpu = knowledge_base.get_gpu("rtx 4070")
        
        assert gpu is not None
        assert gpu.name == "RTX 4070"
        assert gpu.vram_gb == 12
        assert gpu.architecture == "Ada Lovelace"
    
    def test_get_amd_gpu(self):
        """Should return info for AMD GPUs."""
        gpu = knowledge_base.get_gpu("rx 7900 xtx")
        
        assert gpu is not None
        assert gpu.name == "RX 7900 XTX"
        assert gpu.vram_gb == 24
        assert gpu.architecture == "RDNA 3"
    
    def test_get_intel_gpu(self):
        """Should return info for Intel Arc GPUs."""
        gpu = knowledge_base.get_gpu("arc a770")
        
        assert gpu is not None
        assert gpu.name == "Arc A770"
        assert gpu.vram_gb == 16
    
    def test_get_nonexistent_gpu(self):
        """Should return None for non-existent GPUs."""
        gpu = knowledge_base.get_gpu("rtx 6090")  # Doesn't exist
        assert gpu is None
    
    def test_is_valid_gpu(self):
        """Should validate GPU existence."""
        assert knowledge_base.is_valid_gpu("rtx 4090")
        assert knowledge_base.is_valid_gpu("rx 7800 xt")
        assert knowledge_base.is_valid_gpu("rtx 5090")  # RTX 50 series exists now
        assert not knowledge_base.is_valid_gpu("rtx 6090")  # Doesn't exist
    
    def test_get_architecture(self):
        """Should return architecture info."""
        arch = knowledge_base.get_architecture("ada lovelace")
        
        assert arch is not None
        assert arch["vendor"] == "NVIDIA"
        assert arch["year"] == 2022
        assert arch["process"] == "4nm"
    
    def test_search_gpu(self):
        """Should search GPUs by partial name."""
        results = knowledge_base.search_gpu("4070")
        
        assert len(results) >= 3  # 4070, 4070 Ti, 4070 Super, 4070 Ti Super
        names = [gpu.name for gpu in results]
        assert any("4070" in name for name in names)
    
    def test_get_generation_gpus(self):
        """Should return all GPUs of an architecture."""
        ada_gpus = knowledge_base.get_generation_gpus("Ada Lovelace")
        
        assert len(ada_gpus) >= 5
        for gpu in ada_gpus:
            assert gpu.architecture == "Ada Lovelace"
    
    def test_compare_gpus(self):
        """Should compare two GPUs."""
        comparison = knowledge_base.compare_gpus("rtx 4070", "rx 7800 xt")
        
        assert comparison is not None
        assert "RTX 4070" in comparison
        assert "RX 7800 XT" in comparison
        assert "VRAM" in comparison
    
    def test_compare_nonexistent_gpu(self):
        """Should return None when comparing non-existent GPU."""
        comparison = knowledge_base.compare_gpus("rtx 4070", "rtx 6090")  # 6090 doesn't exist
        assert comparison is None
    
    def test_format_gpu_info(self):
        """Should format GPU info as string."""
        gpu = knowledge_base.get_gpu("rtx 4090")
        formatted = knowledge_base.format_gpu_info(gpu)
        
        assert "RTX 4090" in formatted
        assert "24GB" in formatted
        assert "Ada Lovelace" in formatted


class TestGPUData:
    """Tests for GPU data accuracy."""
    
    @pytest.mark.parametrize("gpu_name,expected_vram", [
        ("rtx 5090", 32),
        ("rtx 5080", 16),
        ("rtx 4090", 24),
        ("rtx 4080", 16),
        ("rtx 4070 ti", 12),
        ("rtx 4060", 8),
        ("rx 7900 xtx", 24),
        ("rx 7800 xt", 16),
        ("rx 9070 xt", 16),
    ])
    def test_vram_values(self, gpu_name, expected_vram):
        """VRAM values should be accurate."""
        gpu = knowledge_base.get_gpu(gpu_name)
        assert gpu is not None
        assert gpu.vram_gb == expected_vram
    
    @pytest.mark.parametrize("gpu_name,expected_bus", [
        ("rtx 5090", 512),
        ("rtx 4090", 384),
        ("rtx 4080", 256),
        ("rtx 4070", 192),
        ("rtx 4060", 128),
    ])
    def test_bus_width_values(self, gpu_name, expected_bus):
        """Bus width values should be accurate."""
        gpu = knowledge_base.get_gpu(gpu_name)
        assert gpu is not None
        assert gpu.bus_width == expected_bus


class TestRTX50Series:
    """Tests for RTX 50 series (Blackwell)."""
    
    @pytest.mark.parametrize("model", ["rtx 5090", "rtx 5080", "rtx 5070 ti", "rtx 5070"])
    def test_rtx50_exists(self, model):
        """RTX 50 series should exist in knowledge base."""
        gpu = knowledge_base.get_gpu(model)
        assert gpu is not None
        assert gpu.architecture == "Blackwell"
        assert gpu.release_year == 2025
    
    def test_rtx5090_specs(self):
        """RTX 5090 should have correct specs."""
        gpu = knowledge_base.get_gpu("rtx 5090")
        assert gpu.vram_gb == 32
        assert gpu.bus_width == 512
        assert gpu.cuda_cores == 21760


class TestRDNA4:
    """Tests for RDNA 4 (RX 9000 series)."""
    
    @pytest.mark.parametrize("model", ["rx 9070 xt", "rx 9070"])
    def test_rdna4_exists(self, model):
        """RDNA 4 GPUs should exist in knowledge base."""
        gpu = knowledge_base.get_gpu(model)
        assert gpu is not None
        assert gpu.architecture == "RDNA 4"
        assert gpu.release_year == 2025


class TestCPUData:
    """Tests for CPU data."""
    
    @pytest.mark.parametrize("cpu_name", [
        "ryzen 7 9800x3d", "ryzen 5 9600x", "ryzen 9 9950x",
        "core ultra 9 285k", "i5-14600k", "i9-14900k",
    ])
    def test_cpu_exists(self, cpu_name):
        """CPU should exist in knowledge base."""
        cpu = knowledge_base.get_cpu(cpu_name)
        assert cpu is not None
    
    def test_ryzen_9800x3d_specs(self):
        """Ryzen 7 9800X3D should have correct specs (best gaming CPU 2025)."""
        cpu = knowledge_base.get_cpu("ryzen 7 9800x3d")
        assert cpu is not None
        assert cpu.cores == 8
        assert cpu.threads == 16
        assert cpu.architecture == "Zen 5"
        assert cpu.socket == "AM5"
        assert cpu.cache_l3_mb == 96  # 3D V-Cache!
    
    def test_core_ultra_285k_specs(self):
        """Core Ultra 9 285K should have correct specs."""
        cpu = knowledge_base.get_cpu("core ultra 9 285k")
        assert cpu is not None
        assert cpu.cores == 24
        assert cpu.architecture == "Arrow Lake"
        assert cpu.socket == "LGA1851"


class TestPlatforms:
    """Tests for platform data."""
    
    @pytest.mark.parametrize("platform", ["am5", "am4", "lga1700", "lga1851"])
    def test_platform_exists(self, platform):
        """Platform should exist in knowledge base."""
        info = knowledge_base.get_platform(platform)
        assert info is not None
    
    def test_am5_platform(self):
        """AM5 should have correct info."""
        platform = knowledge_base.get_platform("am5")
        assert platform is not None
        assert platform.memory_type == "DDR5"
        assert platform.vendor == "AMD"
        assert "5.0" in platform.pcie_version
    
    def test_lga1851_platform(self):
        """LGA1851 should have correct info."""
        platform = knowledge_base.get_platform("lga1851")
        assert platform is not None
        assert platform.memory_type == "DDR5"
        assert platform.vendor == "Intel"


class TestBuildRecommendations:
    """Tests for build recommendations."""
    
    @pytest.mark.parametrize("tier", ["gaming_budget", "gaming_mid", "gaming_high", "workstation"])
    def test_build_recommendation_exists(self, tier):
        """Build recommendation should exist."""
        build = knowledge_base.get_build_recommendation(tier)
        assert build is not None
        assert "cpu" in build
        assert "gpu" in build
        assert "ram" in build
    
    def test_format_build_recommendation(self):
        """Should format build recommendation."""
        formatted = knowledge_base.format_build_recommendation("gaming_mid")
        assert formatted is not None
        assert "Ryzen" in formatted or "Intel" in formatted
        assert "RTX" in formatted or "RX" in formatted


class TestSummary:
    """Tests for summary methods."""
    
    def test_2025_summary(self):
        """Should return 2025 hardware summary."""
        summary = knowledge_base.get_2025_summary()
        assert "2025" in summary
        assert "DDR5" in summary
        assert "RTX 50" in summary or "RTX 40" in summary
        assert "AM5" in summary
    
    def test_gaming_cpu_recommendations(self):
        """Should return gaming CPU recommendations."""
        recs = knowledge_base.get_gaming_cpu_recommendations()
        assert len(recs) >= 3
        assert any("9800X3D" in r for r in recs)
    
    def test_current_platforms(self):
        """Should return current platforms."""
        platforms = knowledge_base.get_current_platforms()
        assert len(platforms) >= 2
        assert any("AM5" in p for p in platforms)


class TestSoftwareBase:
    """Tests for software knowledge base."""
    
    def test_os_info_windows_11(self):
        """Should return Windows 11 info."""
        os_info = knowledge_base.get_os_info("windows_11")
        assert os_info is not None
        assert "24H2" in os_info.get("version", "")
        assert os_info.get("status") == "Основная система 2025"
    
    def test_os_info_windows_12_not_released(self):
        """Windows 12 should be marked as not released."""
        os_info = knowledge_base.get_os_info("windows_12")
        assert os_info is not None
        assert "НЕ ВЫШЛА" in os_info.get("status", "")
    
    def test_os_info_linux_bazzite(self):
        """Should return Bazzite info."""
        os_info = knowledge_base.get_os_info("bazzite")
        assert os_info is not None
        assert "SteamOS" in os_info.get("notes", "")
    
    def test_tuning_software_list(self):
        """Should return list of tuning software."""
        software = knowledge_base.get_tuning_software()
        assert len(software) > 5
        names = [s.name for s in software]
        assert "MSI Afterburner + RTSS" in names
        assert "HWInfo64" in names
        assert "OCCT" in names
    
    def test_tuning_software_by_category(self):
        """Should filter software by category."""
        stress_tests = knowledge_base.get_tuning_software("stress_test")
        assert len(stress_tests) >= 3
        for sw in stress_tests:
            assert sw.category == "stress_test"
    
    def test_tuning_guide_amd_cpu(self):
        """Should return AMD CPU tuning guide."""
        guide = knowledge_base.get_tuning_guide("ryzen")
        assert guide is not None
        assert "PBO" in guide.method or "Curve" in guide.method
        assert len(guide.steps) >= 3
        assert len(guide.tools) >= 2
    
    def test_tuning_guide_nvidia_gpu(self):
        """Should return NVIDIA GPU tuning guide."""
        guide = knowledge_base.get_tuning_guide("rtx")
        assert guide is not None
        assert "андервольт" in guide.method.lower() or "undervolt" in guide.method.lower()
        assert any("Afterburner" in tool for tool in guide.tools)
    
    def test_tuning_guide_ddr5(self):
        """Should return DDR5 tuning guide."""
        guide = knowledge_base.get_tuning_guide("ddr5")
        assert guide is not None
        assert "tREFI" in guide.method or any("tREFI" in step for step in guide.steps)
        assert len(guide.warnings) >= 2  # DDR5 has temperature warnings
    
    def test_format_tuning_guide(self):
        """Should format tuning guide."""
        guide = knowledge_base.get_tuning_guide("nvidia")
        formatted = knowledge_base.format_tuning_guide(guide)
        assert "🔧" in formatted
        assert "Шаги:" in formatted
        assert "Инструменты:" in formatted
    
    def test_windows_setup_checklist(self):
        """Should return Windows setup checklist."""
        checklist = knowledge_base.get_windows_setup_checklist()
        assert "После установки Windows" in checklist
        assert "WinUtil" in checklist or "christitus" in checklist
        assert "XMP" in checklist or "EXPO" in checklist
    
    def test_stability_checklist(self):
        """Should return stability checklist."""
        checklist = knowledge_base.get_stability_checklist()
        assert "стабильности" in checklist.lower()
        assert "WHEA" in checklist
        assert "TestMem5" in checklist or "DDR5" in checklist.upper()
    
    def test_software_summary(self):
        """Should return software summary."""
        summary = knowledge_base.get_software_summary()
        assert "2025" in summary
        assert "Windows 11" in summary
        assert "Windows 12" in summary and "НЕ ВЫШЛА" in summary
        assert "андервольт" in summary.lower() or "Андервольт" in summary
