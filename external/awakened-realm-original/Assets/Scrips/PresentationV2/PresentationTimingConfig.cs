using System;
using UnityEngine;

namespace AwakenedRealm.Presentation
{
    /// <summary>
    /// Pure timing data for the presentation layer. Values are tuned for Android-friendly
    /// pacing; DOTween/animation integration consumes these numbers later. No runtime
    /// tweening or scene dependencies exist in this slice.
    /// </summary>
    public sealed class PresentationTimingConfig : ScriptableObject
    {
        public const string ResourcePath = "AwakenedRealmsGenerated/TimingConfig";

        [Serializable]
        public sealed class FadeTimings
        {
            [Tooltip("Screen-to-screen fade out duration (seconds).")]
            public float fadeOut = 0.35f;
            [Tooltip("Screen-to-screen fade in duration (seconds).")]
            public float fadeIn = 0.35f;
            [Tooltip("Full black hold between fade out and fade in for heavy screens.")]
            public float holdBlack = 0.15f;
        }

        [Serializable]
        public sealed class SummonTimings
        {
            [Tooltip("Portal idle loop before reveal begins.")]
            public float portalIdle = 1.2f;
            [Tooltip("Rarity portal burst / flash duration.")]
            public float rarityReveal = 0.9f;
            [Tooltip("Card flip / hero silhouette reveal.")]
            public float heroReveal = 0.8f;
            [Tooltip("Post-reveal linger before results are skippable.")]
            public float resultLinger = 1.0f;
        }

        [Serializable]
        public sealed class UltimateTimings
        {
            [Tooltip("Backplate screen dim fade-in.")]
            public float backplateIn = 0.25f;
            [Tooltip("Character cut-in slide/pose duration.")]
            public float cutIn = 0.55f;
            [Tooltip("Beat where the damage burst fires relative to cut-in end.")]
            public float impactDelay = 0.15f;
            [Tooltip("Backplate fade-out after impact.")]
            public float backplateOut = 0.3f;
        }

        [Serializable]
        public sealed class StarUpTimings
        {
            [Tooltip("Aura build-up before star burst.")]
            public float auraBuild = 0.7f;
            [Tooltip("Star burst flash duration.")]
            public float starBurst = 0.45f;
            [Tooltip("Stat/level reveal cards duration.")]
            public float statReveal = 0.9f;
            [Tooltip("Settle time before returning to detail UI.")]
            public float settle = 0.6f;
        }

        [Serializable]
        public sealed class BattleFeedbackTimings
        {
            [Tooltip("Hit flash duration on the target sprite.")]
            public float hitFlash = 0.08f;
            [Tooltip("Small hit camera/object shake duration.")]
            public float hitShake = 0.12f;
            [Tooltip("Crit flash duration (longer punch).")]
            public float critFlash = 0.14f;
            [Tooltip("Crit shake duration / stronger impulse window.")]
            public float critShake = 0.22f;
            [Tooltip("Floating damage number lifetime.")]
            public float damageNumber = 0.7f;
        }

        public FadeTimings fades = new FadeTimings();
        public SummonTimings summon = new SummonTimings();
        public UltimateTimings ultimate = new UltimateTimings();
        public StarUpTimings starUp = new StarUpTimings();
        public BattleFeedbackTimings battleFeedback = new BattleFeedbackTimings();

        /// <summary>Enumerate every duration field for range validation.</summary>
        public void ForEachDuration(Action<string, float> visit)
        {
            if (visit == null)
            {
                return;
            }

            visit("fades.fadeOut", fades.fadeOut);
            visit("fades.fadeIn", fades.fadeIn);
            visit("fades.holdBlack", fades.holdBlack);
            visit("summon.portalIdle", summon.portalIdle);
            visit("summon.rarityReveal", summon.rarityReveal);
            visit("summon.heroReveal", summon.heroReveal);
            visit("summon.resultLinger", summon.resultLinger);
            visit("ultimate.backplateIn", ultimate.backplateIn);
            visit("ultimate.cutIn", ultimate.cutIn);
            visit("ultimate.impactDelay", ultimate.impactDelay);
            visit("ultimate.backplateOut", ultimate.backplateOut);
            visit("starUp.auraBuild", starUp.auraBuild);
            visit("starUp.starBurst", starUp.starBurst);
            visit("starUp.statReveal", starUp.statReveal);
            visit("starUp.settle", starUp.settle);
            visit("battleFeedback.hitFlash", battleFeedback.hitFlash);
            visit("battleFeedback.hitShake", battleFeedback.hitShake);
            visit("battleFeedback.critFlash", battleFeedback.critFlash);
            visit("battleFeedback.critShake", battleFeedback.critShake);
            visit("battleFeedback.damageNumber", battleFeedback.damageNumber);
        }
    }
}
