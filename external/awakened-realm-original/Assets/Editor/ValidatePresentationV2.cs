using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using AwakenedRealm.Presentation;
using UnityEditor;
using UnityEngine;

/// <summary>
/// Validates the generated presentation catalog slice. Runs in the editor (menu or
/// batch). Fails closed on any problem so CI/batchmode catches issues before runtime.
/// </summary>
public static class ValidatePresentationV2
{
    const string ReportPath = "/home/ubuntu/logres/artifacts/legacy-awakened/presentation-v2-validation.txt";

    public static void Run()
    {
        var failures = new List<string>();
        var lines = new List<string>();

        var catalog = AssetDatabase.LoadAssetAtPath<GeneratedVisualCatalog>(
            "Assets/Resources/AwakenedRealmsGenerated/VisualCatalog.asset");
        var effectCatalog = AssetDatabase.LoadAssetAtPath<GeneratedEffectCatalog>(
            "Assets/Resources/AwakenedRealmsGenerated/EffectCatalog.asset");
        var timing = AssetDatabase.LoadAssetAtPath<PresentationTimingConfig>(
            "Assets/Resources/AwakenedRealmsGenerated/TimingConfig.asset");

        if (catalog == null)
        {
            failures.Add("VisualCatalog.asset missing; run Awakened Realms/Generated Art/Build Visual Catalog");
        }
        if (effectCatalog == null)
        {
            failures.Add("EffectCatalog.asset missing; run Awakened Realms/Generated Art/Build Visual Catalog");
        }
        if (timing == null)
        {
            failures.Add("TimingConfig.asset missing; run Awakened Realms/Generated Art/Build Visual Catalog");
        }

        if (catalog != null)
        {
            ValidateCatalog(catalog, failures, lines);
        }
        if (effectCatalog != null)
        {
            ValidateEffectCatalog(effectCatalog, failures, lines);
        }
        if (timing != null)
        {
            ValidateTimings(timing, failures, lines);
        }

        var reportDir = Path.GetDirectoryName(ReportPath);
        if (!string.IsNullOrEmpty(reportDir))
        {
            Directory.CreateDirectory(reportDir);
        }
        File.WriteAllLines(ReportPath, lines.Concat(failures.Select(x => "FAIL " + x)));

        if (failures.Count > 0)
        {
            throw new InvalidOperationException("Presentation V2 validation failed: " + string.Join(" | ", failures));
        }

        Debug.Log("AWAKENED_REALMS_PRESENTATION_V2_VALIDATION_PASS");
    }

    static void ValidateCatalog(GeneratedVisualCatalog catalog, List<string> failures, List<string> lines)
    {
        var entries = catalog.Entries;
        if (entries == null || entries.Count == 0)
        {
            failures.Add("VisualCatalog has no entries");
            return;
        }

        // Unique keys
        var seen = new HashSet<string>(StringComparer.Ordinal);
        foreach (var e in entries)
        {
            if (e == null)
            {
                failures.Add("null entry in VisualCatalog");
                continue;
            }
            if (string.IsNullOrEmpty(e.key))
            {
                failures.Add("entry with empty key");
                continue;
            }
            if (!seen.Add(e.key))
            {
                failures.Add($"duplicate catalog key '{e.key}'");
            }
            if (e.sprite == null)
            {
                failures.Add($"catalog key '{e.key}' has null sprite");
            }
            if (string.IsNullOrEmpty(e.sourceAssetPath))
            {
                failures.Add($"catalog key '{e.key}' has empty sourceAssetPath");
            }
        }
        lines.Add($"catalog.entries={entries.Count}");

        // Required key families
        RequireKeys("core screens", GeneratedVisualKeys.CoreScreenKeys, entries, failures);
        RequireKeys("chapters 1..10", GeneratedVisualKeys.ChapterKeys, entries, failures);
        RequireKeys("bosses", GeneratedVisualKeys.BossKeys, entries, failures);
        RequireKeys("role icons", GeneratedVisualKeys.RoleKeys, entries, failures);
        RequireKeys("campaign nodes", GeneratedVisualKeys.NodeKeys, entries, failures);
        RequireKeys("currencies", GeneratedVisualKeys.CurrencyKeys, entries, failures);
        RequireKeys("ceremonies", GeneratedVisualKeys.CeremonyKeys, entries, failures);

        foreach (var rarity in GeneratedVisualKeys.CuratedRarities)
        {
            RequireKeys($"rarity {rarity}", new[]
            {
                GeneratedVisualKeys.RarityFrame(rarity),
                GeneratedVisualKeys.SummonPortal(rarity),
                GeneratedVisualKeys.SummonReveal(rarity),
                GeneratedVisualKeys.StarUpCeremony(rarity),
            }, entries, failures);
        }

        foreach (var faction in GeneratedVisualKeys.FactionIds)
        {
            foreach (var tier in GeneratedVisualKeys.EvolutionTiers)
            {
                RequireKeys($"evolution {faction} t{tier}",
                    new[] { GeneratedVisualKeys.EvolutionAura(faction, tier) },
                    entries, failures);
            }
        }

        // Concept-only entries must not be marked as final.
        foreach (var e in entries)
        {
            if (e != null && e.kind == GeneratedVisualKind.ConceptEffectSource && !e.isConceptReferenceOnly)
            {
                failures.Add($"concept effect source '{e.key}' is not flagged concept-reference-only");
            }
        }
    }

    static void RequireKeys(string label, IEnumerable<string> keys,
        IReadOnlyList<GeneratedVisualCatalog.Entry> entries, List<string> failures)
    {
        var present = new HashSet<string>(entries.Where(e => e != null).Select(e => e.key), StringComparer.Ordinal);
        foreach (var key in keys)
        {
            if (!present.Contains(key))
            {
                failures.Add($"missing required {label} key '{key}'");
            }
        }
    }

    static void ValidateEffectCatalog(GeneratedEffectCatalog catalog, List<string> failures, List<string> lines)
    {
        var effects = catalog.Effects;
        if (effects == null || effects.Count == 0)
        {
            failures.Add("EffectCatalog has no effects");
            return;
        }

        var seen = new HashSet<string>(StringComparer.Ordinal);
        foreach (var fx in effects)
        {
            if (fx == null)
            {
                failures.Add("null effect entry");
                continue;
            }
            if (string.IsNullOrEmpty(fx.effectId))
            {
                failures.Add("effect entry with empty effectId");
                continue;
            }
            if (!seen.Add(fx.effectId))
            {
                failures.Add($"duplicate effectId '{fx.effectId}'");
            }
            if (fx.sourceSprite == null)
            {
                failures.Add($"effect '{fx.effectId}' has null source sprite");
            }
            if (string.IsNullOrEmpty(fx.sourceAssetPath))
            {
                failures.Add($"effect '{fx.effectId}' has empty sourceAssetPath");
            }
            // All curated concept FX are source references that must be rebuilt.
            if (!fx.requiresRuntimeRebuild)
            {
                failures.Add($"concept effect '{fx.effectId}' is marked final (requiresRuntimeRebuild=false)");
            }
        }
        lines.Add($"effects.count={effects.Count}");
    }

    static void ValidateTimings(PresentationTimingConfig timing, List<string> failures, List<string> lines)
    {
        var count = 0;
        timing.ForEachDuration((name, value) =>
        {
            count++;
            if (value < 0f)
            {
                failures.Add($"timing '{name}' is negative ({value})");
            }
            if (value > 10f)
            {
                failures.Add($"timing '{name}' is too long for mobile ({value}s)");
            }
        });
        if (count == 0)
        {
            failures.Add("timing config exposes no durations");
        }
        lines.Add($"timing.fields={count}");
    }
}
