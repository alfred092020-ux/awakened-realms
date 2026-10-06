using System;
using System.Collections.Generic;

namespace AwakenedRealm.Progression
{
    public enum CampaignStageType
    {
        Normal,
        Elite,
        Boss
    }

    public sealed class CampaignStage
    {
        public readonly int StageId;
        public readonly int Chapter;
        public readonly int IndexInChapter;
        public readonly CampaignStageType Type;

        public CampaignStage(int stageId, int chapter, int indexInChapter, CampaignStageType type)
        {
            StageId = stageId;
            Chapter = chapter;
            IndexInChapter = indexInChapter;
            Type = type;
        }

        public override string ToString()
        {
            return string.Format("Stage {0} (Chapter {1}-{2}, {3})", StageId, Chapter, IndexInChapter, Type);
        }
    }

    /// <summary>
    /// Deterministic campaign layout: 10 chapters of 12 stages each
    /// (10 Normal, 1 Elite, 1 Boss). Stage IDs are stable integers of the
    /// form chapter * 100 + indexInChapter (e.g. 101..112, 201..212, 1001..1012).
    /// Pure data; no Unity scene or UI dependency.
    /// </summary>
    public static class CampaignCatalog
    {
        public const int ChapterCount = 10;
        public const int NormalStagesPerChapter = 10;
        public const int StagesPerChapter = NormalStagesPerChapter + 2;
        public const int EliteIndex = NormalStagesPerChapter + 1;
        public const int BossIndex = NormalStagesPerChapter + 2;

        public static readonly int MinStage = MakeStageId(1, 1);
        public static readonly int MaxStage = MakeStageId(ChapterCount, StagesPerChapter);

        static readonly CampaignStage[] OrderedStages;
        static readonly Dictionary<int, CampaignStage> ById;

        static CampaignCatalog()
        {
            var stages = new List<CampaignStage>(ChapterCount * StagesPerChapter);
            for (int chapter = 1; chapter <= ChapterCount; chapter++)
            {
                for (int index = 1; index <= StagesPerChapter; index++)
                {
                    CampaignStageType type =
                        index <= NormalStagesPerChapter ? CampaignStageType.Normal :
                        index == EliteIndex ? CampaignStageType.Elite :
                        CampaignStageType.Boss;
                    stages.Add(new CampaignStage(MakeStageId(chapter, index), chapter, index, type));
                }
            }

            OrderedStages = stages.ToArray();
            ById = new Dictionary<int, CampaignStage>(OrderedStages.Length);
            for (int i = 0; i < OrderedStages.Length; i++)
                ById.Add(OrderedStages[i].StageId, OrderedStages[i]);
        }

        public static int MakeStageId(int chapter, int indexInChapter)
        {
            return chapter * 100 + indexInChapter;
        }

        /// <summary>Returns a defensive copy of all stages in ascending ID order.</summary>
        public static CampaignStage[] Stages
        {
            get { return (CampaignStage[])OrderedStages.Clone(); }
        }

        public static bool IsStage(int stageId)
        {
            return ById.ContainsKey(stageId);
        }

        public static bool TryGetStage(int stageId, out CampaignStage stage)
        {
            return ById.TryGetValue(stageId, out stage);
        }

        public static CampaignStage GetStage(int stageId)
        {
            CampaignStage stage;
            if (!ById.TryGetValue(stageId, out stage))
                throw new ArgumentOutOfRangeException(nameof(stageId), stageId, "Unknown campaign stage ID.");
            return stage;
        }

        public static CampaignStageType StageTypeOf(int stageId)
        {
            return GetStage(stageId).Type;
        }

        public static int ChapterOf(int stageId)
        {
            return GetStage(stageId).Chapter;
        }

        /// <summary>
        /// Returns the next playable stage strictly after <paramref name="stageId"/>,
        /// or null once the final Boss stage is cleared. Passing 0 (nothing
        /// cleared) returns the first stage.
        /// </summary>
        public static CampaignStage NextStageAfter(int stageId)
        {
            for (int i = 0; i < OrderedStages.Length; i++)
                if (OrderedStages[i].StageId > stageId)
                    return OrderedStages[i];
            return null;
        }
    }
}
