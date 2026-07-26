"""Build quality tier evaluator for weapon builds."""
import logging
from typing import Dict, Optional
from database import TierRating

logger = logging.getLogger(__name__)


class TierEvaluator:
    """Service for evaluating weapon build quality and assigning tiers."""
    
    # Thresholds for tier calculation
    ERGONOMICS_EXCELLENT = 50
    ERGONOMICS_GOOD = 35
    ERGONOMICS_AVERAGE = 20
    
    RECOIL_EXCELLENT = 40
    RECOIL_GOOD = 60
    RECOIL_AVERAGE = 80
    
    # Cost efficiency thresholds (cost per point of stats)
    COST_EFFICIENCY_EXCELLENT = 1500
    COST_EFFICIENCY_GOOD = 2500
    COST_EFFICIENCY_AVERAGE = 4000
    
    def evaluate_build(
        self,
        ergonomics: Optional[int],
        recoil_vertical: Optional[int],
        recoil_horizontal: Optional[int],
        total_cost: int,
        has_all_required_slots: bool,
        has_sight: bool,
        has_stock: bool,
        has_grip: bool,
        weapon_base_ergonomics: Optional[int] = None,
        weapon_base_recoil: Optional[int] = None
    ) -> TierRating:
        """
        Evaluate a build and return its tier rating.
        
        Args:
            ergonomics: Final ergonomics value
            recoil_vertical: Final vertical recoil
            recoil_horizontal: Final horizontal recoil (optional)
            total_cost: Total build cost in rubles
            has_all_required_slots: Whether all required slots are filled
            has_sight: Whether build has a sight
            has_stock: Whether build has a stock
            has_grip: Whether build has a grip
            weapon_base_ergonomics: Base weapon ergonomics for comparison
            weapon_base_recoil: Base weapon recoil for comparison
            
        Returns:
            TierRating enum value (S/A/B/C/D)
        """
        score = 0
        max_score = 100
        
        # 1. Completeness check (20 points)
        if not has_all_required_slots:
            score -= 20
        else:
            score += 20
        
        # 2. Key modules check (15 points)
        key_modules_score = 0
        if has_sight:
            key_modules_score += 5
        if has_stock:
            key_modules_score += 5
        if has_grip:
            key_modules_score += 5
        score += key_modules_score
        
        # 3. Ergonomics evaluation (30 points)
        if ergonomics is not None:
            if ergonomics >= self.ERGONOMICS_EXCELLENT:
                score += 30
            elif ergonomics >= self.ERGONOMICS_GOOD:
                score += 22
            elif ergonomics >= self.ERGONOMICS_AVERAGE:
                score += 15
            else:
                score += 5
        
        # 4. Recoil evaluation (30 points)
        if recoil_vertical is not None:
            # Lower recoil is better
            if recoil_vertical <= self.RECOIL_EXCELLENT:
                score += 30
            elif recoil_vertical <= self.RECOIL_GOOD:
                score += 22
            elif recoil_vertical <= self.RECOIL_AVERAGE:
                score += 15
            else:
                score += 5
        
        # 5. Cost efficiency (5 points bonus/penalty)
        if ergonomics and recoil_vertical and total_cost > 0:
            # Calculate efficiency: higher ergo + lower recoil = better
            stat_value = ergonomics + (100 - recoil_vertical)
            if stat_value > 0:
                cost_per_stat = total_cost / stat_value
                
                if cost_per_stat <= self.COST_EFFICIENCY_EXCELLENT:
                    score += 5
                elif cost_per_stat <= self.COST_EFFICIENCY_GOOD:
                    score += 3
                elif cost_per_stat <= self.COST_EFFICIENCY_AVERAGE:
                    score += 1
                else:
                    score -= 5
        
        # 6. Improvement over base weapon (bonus points if we have base stats)
        if weapon_base_ergonomics and weapon_base_recoil and ergonomics and recoil_vertical:
            ergo_improvement = ergonomics - weapon_base_ergonomics
            recoil_improvement = weapon_base_recoil - recoil_vertical  # Lower is better
            
            total_improvement = ergo_improvement + recoil_improvement
            if total_improvement > 50:
                score += 10
            elif total_improvement > 30:
                score += 5
            elif total_improvement < 0:
                score -= 5
        
        # Calculate percentage
        percentage = (score / max_score) * 100
        
        # Assign tier based on percentage
        if percentage >= 85:
            return TierRating.S_TIER
        elif percentage >= 70:
            return TierRating.A_TIER
        elif percentage >= 50:
            return TierRating.B_TIER
        elif percentage >= 30:
            return TierRating.C_TIER
        else:
            return TierRating.D_TIER
    
    def get_tier_description(self, tier: TierRating, language: str = "ru") -> str:
        """
        Get human-readable description of a tier.
        
        Args:
            tier: TierRating enum
            language: Language code (ru/en)
            
        Returns:
            Tier description string
        """
        descriptions = {
            "ru": {
                TierRating.S_TIER: "🏆 Отличная сборка! Превосходный баланс характеристик",
                TierRating.A_TIER: "🥇 Очень хорошая сборка с отличными показателями",
                TierRating.B_TIER: "🥈 Хорошая сборка с приемлемыми характеристиками",
                TierRating.C_TIER: "🥉 Средняя сборка, есть возможности для улучшения",
                TierRating.D_TIER: "📊 Слабая сборка, требует значительных улучшений"
            },
            "en": {
                TierRating.S_TIER: "🏆 Excellent build! Superior stat balance",
                TierRating.A_TIER: "🥇 Very good build with great performance",
                TierRating.B_TIER: "🥈 Good build with acceptable stats",
                TierRating.C_TIER: "🥉 Average build, room for improvement",
                TierRating.D_TIER: "📊 Weak build, needs significant improvements"
            }
        }
        
        return descriptions.get(language, descriptions["ru"]).get(
            tier, 
            "Build tier"
        )
    
    def get_improvement_suggestions(
        self,
        tier: TierRating,
        ergonomics: Optional[int],
        recoil_vertical: Optional[int],
        has_sight: bool,
        has_stock: bool,
        has_grip: bool,
        language: str = "ru"
    ) -> list[str]:
        """
        Get improvement suggestions based on build evaluation.
        
        Args:
            tier: Current tier rating
            ergonomics: Current ergonomics
            recoil_vertical: Current recoil
            has_sight: Has sight module
            has_stock: Has stock module
            has_grip: Has grip module
            language: Language code
            
        Returns:
            List of suggestion strings
        """
        suggestions = []
        
        if language == "ru":
            if not has_sight:
                suggestions.append("• Добавьте прицел для лучшей точности")
            if not has_stock:
                suggestions.append("• Установите приклад для снижения отдачи")
            if not has_grip:
                suggestions.append("• Добавьте рукоять для улучшения эргономики")
            
            if ergonomics and ergonomics < self.ERGONOMICS_AVERAGE:
                suggestions.append("• Улучшите эргономику (лёгкие модули, тактические рукояти)")
            
            if recoil_vertical and recoil_vertical > self.RECOIL_GOOD:
                suggestions.append("• Снизьте отдачу (дульный тормоз, приклад, цевье)")
        else:
            if not has_sight:
                suggestions.append("• Add a sight for better accuracy")
            if not has_stock:
                suggestions.append("• Install a stock to reduce recoil")
            if not has_grip:
                suggestions.append("• Add a grip to improve ergonomics")
            
            if ergonomics and ergonomics < self.ERGONOMICS_AVERAGE:
                suggestions.append("• Improve ergonomics (lightweight modules, tactical grips)")
            
            if recoil_vertical and recoil_vertical > self.RECOIL_GOOD:
                suggestions.append("• Reduce recoil (muzzle brake, stock, handguard)")
        
        return suggestions
