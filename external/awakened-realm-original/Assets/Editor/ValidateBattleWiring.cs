using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using AwakenedRealm;
using AwakenedRealm.Scriptables;
using AwakenedRealm.UI;

public static class ValidateBattleWiring
{
    const string ReportPath = "/home/ubuntu/logres/artifacts/legacy-awakened/battle-wiring-validation.txt";

    public static void Run()
    {
        var failures = new List<string>();
        var lines = new List<string>();

        var scene = EditorSceneManager.OpenScene("Assets/Scenes/Battle.unity", OpenSceneMode.Single);
        var battleManager = UnityEngine.Object.FindAnyObjectByType<BattleManager>(FindObjectsInactive.Include);
        if (battleManager == null)
        {
            failures.Add("BattleManager missing");
        }
        else
        {
            var so = new SerializedObject(battleManager);
            ValidateArray(so.FindProperty("_heroSpawnTransforms"), 9, "player spawn transforms", failures, lines);
            ValidateArray(so.FindProperty("_enemySpawnTransforms"), 9, "enemy spawn transforms", failures, lines);
            ValidateArray(so.FindProperty("_bossSpawnTransforms"), 1, "boss spawn transforms", failures, lines);
            var active = so.FindProperty("_totalActiveHeroesAtATime");
            if (active == null || active.intValue != 5) failures.Add("active battle party size must equal 5");
            else lines.Add("active battle party size=5");
        }

        var grid = UnityEngine.Object.FindAnyObjectByType<UI_BattlePlacementGrid>(FindObjectsInactive.Include);
        if (grid == null)
        {
            failures.Add("UI_BattlePlacementGrid missing");
        }
        else
        {
            var blocks = grid.GetGridBlocksUI();
            if (blocks == null || blocks.Length != 9)
                failures.Add($"placement grid block count expected 9 found {blocks?.Length ?? 0}");
            else
            {
                var ids = blocks.Select(x => x == null ? -1 : x.GridID).ToArray();
                if (!ids.SequenceEqual(Enumerable.Range(1, 9)))
                    failures.Add("placement grid IDs are not normalized 1..9");
                if (blocks.Any(x => x == null))
                    failures.Add("placement grid contains null block");
                lines.Add("placement grid blocks=9");
            }
        }

        var heroes = AssetDatabase.FindAssets("t:HeroSO", new[] { "Assets/Scrips/Scriptables/SO/Hero" })
            .Select(AssetDatabase.GUIDToAssetPath)
            .Where(path => !path.EndsWith("Hero Collection.asset", StringComparison.OrdinalIgnoreCase))
            .Select(path => AssetDatabase.LoadAssetAtPath<HeroSO>(path))
            .Where(x => x != null)
            .ToArray();

        if (heroes.Length != 15) failures.Add($"HeroSO count expected 15 found {heroes.Length}");

        var idsSeen = new HashSet<string>(StringComparer.Ordinal);
        foreach (var hero in heroes)
        {
            var profile = hero.GetHeroProfile();
            var id = profile?.HeroID;
            if (string.IsNullOrWhiteSpace(id)) failures.Add($"{hero.name} has empty HeroID");
            else if (!idsSeen.Add(id)) failures.Add($"duplicate HeroID {id}");

            if (hero.GetHeroControllerPrefab() == null) failures.Add($"{hero.name} has null prefab");
            if (hero.GetHeroSprite() == null) failures.Add($"{hero.name} has null sprite");

            var prefab = hero.GetHeroControllerPrefab();
            if (prefab != null)
            {
                var go = prefab.gameObject;
                if (go.GetComponent<HeroController>() == null) failures.Add($"{hero.name} prefab missing HeroController");
                var animator = go.GetComponent<Animator>();
                if (animator == null || animator.runtimeAnimatorController == null)
                    failures.Add($"{hero.name} prefab missing animator controller");
                if (go.GetComponent<SpriteRenderer>() == null)
                    failures.Add($"{hero.name} prefab missing SpriteRenderer");
            }
        }

        lines.Add($"hero assets={heroes.Length}");
        lines.Add($"stable unique hero ids={idsSeen.Count}");

        File.WriteAllLines(ReportPath, lines.Concat(failures.Select(x => "FAIL " + x)));

        if (failures.Count > 0)
            throw new InvalidOperationException("Battle wiring validation failed: " + string.Join(" | ", failures));

        Debug.Log("AWAKENED_REALMS_BATTLE_WIRING_VALIDATION_PASS");
    }

    static void ValidateArray(SerializedProperty property, int expected, string label, List<string> failures, List<string> lines)
    {
        if (property == null || !property.isArray)
        {
            failures.Add(label + " property missing");
            return;
        }

        if (property.arraySize != expected)
            failures.Add($"{label} expected {expected} found {property.arraySize}");

        for (int i = 0; i < property.arraySize; i++)
        {
            if (property.GetArrayElementAtIndex(i).objectReferenceValue == null)
                failures.Add($"{label}[{i}] is null");
        }

        lines.Add($"{label}={property.arraySize}");
    }
}
