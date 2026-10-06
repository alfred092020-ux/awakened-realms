using System;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using AwakenedRealm.Scriptables;
using AwakenedRealm.UI;

public static class ExerciseFormationPlacement
{
    public static void Run()
    {
        EditorSceneManager.OpenScene("Assets/Scenes/Battle.unity", OpenSceneMode.Single);
        var grid = UnityEngine.Object.FindAnyObjectByType<UI_BattlePlacementGrid>(FindObjectsInactive.Include);
        if (grid == null) throw new InvalidOperationException("Placement grid missing.");

        var blocks = grid.GetGridBlocksUI();
        if (blocks == null || blocks.Length != 9) throw new InvalidOperationException("Expected nine placement blocks.");

        var heroes = AssetDatabase.FindAssets("t:HeroSO", new[] { "Assets/Scrips/Scriptables/SO/Hero" })
            .Select(AssetDatabase.GUIDToAssetPath)
            .Where(path => !path.EndsWith("Hero Collection.asset", StringComparison.OrdinalIgnoreCase))
            .OrderBy(path => path, StringComparer.Ordinal)
            .Select(path => AssetDatabase.LoadAssetAtPath<HeroSO>(path))
            .Where(x => x != null)
            .Take(6)
            .ToArray();

        if (heroes.Length < 6) throw new InvalidOperationException("Not enough heroes for placement exercise.");

        foreach (var block in blocks) block.ClearHero();

        int[] targetSlots = { 0, 2, 4, 6, 8 };
        for (int i = 0; i < targetSlots.Length; i++)
        {
            if (!grid.TryPlaceHero(heroes[i], blocks[targetSlots[i]]))
                throw new InvalidOperationException($"Failed to place hero {i} into slot {targetSlots[i]}.");
        }

        var first = grid.GetFormation();
        if (first.Count != 5 || !first.Select(x => x.SlotIndex).SequenceEqual(targetSlots))
            throw new InvalidOperationException("Formation did not preserve selected 3x3 slot indices.");

        if (grid.TryPlaceHero(heroes[5], blocks[1]))
            throw new InvalidOperationException("Grid accepted a sixth hero despite five-hero party cap.");

        if (!grid.TryPlaceHero(heroes[0], blocks[7]))
            throw new InvalidOperationException("Moving an existing hero between slots failed.");

        var moved = grid.GetFormation();
        int[] expectedAfterMove = { 2, 4, 6, 7, 8 };
        if (moved.Count != 5 || !moved.Select(x => x.SlotIndex).SequenceEqual(expectedAfterMove))
            throw new InvalidOperationException("Moving a hero did not preserve formation cardinality and slot mapping.");

        Debug.Log("AWAKENED_REALMS_FORMATION_PLACEMENT_EXERCISE_PASS");
    }
}
