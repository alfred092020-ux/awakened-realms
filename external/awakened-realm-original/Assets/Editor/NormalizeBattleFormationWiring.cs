using System;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using AwakenedRealm;
using AwakenedRealm.Scriptables;
using AwakenedRealm.UI;

public static class NormalizeBattleFormationWiring
{
    const string BattleScenePath = "Assets/Scenes/Battle.unity";
    const string HeroFolder = "Assets/Scrips/Scriptables/SO/Hero";

    [MenuItem("Awakened Realms/Migrate/Normalize Battle Formation Wiring")]
    public static void Run()
    {
        AssignStableHeroIds();
        NormalizeBattleScene();
        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
        Debug.Log("AWAKENED_REALMS_BATTLE_WIRING_NORMALIZED");
    }

    static void AssignStableHeroIds()
    {
        var heroPaths = AssetDatabase.FindAssets("t:HeroSO", new[] { HeroFolder })
            .Select(AssetDatabase.GUIDToAssetPath)
            .Where(path => !path.EndsWith("Hero Collection.asset", StringComparison.OrdinalIgnoreCase))
            .OrderBy(path => path, StringComparer.Ordinal)
            .ToArray();

        for (int i = 0; i < heroPaths.Length; i++)
        {
            var hero = AssetDatabase.LoadAssetAtPath<HeroSO>(heroPaths[i]);
            if (hero == null) continue;

            var serializedHero = new SerializedObject(hero);
            var profile = serializedHero.FindProperty("_heroProfile");
            var heroId = profile?.FindPropertyRelative("HeroID");
            if (heroId == null) continue;

            string expected = $"ar-legacy-{i + 1:000}";
            if (string.IsNullOrWhiteSpace(heroId.stringValue))
                heroId.stringValue = expected;

            serializedHero.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(hero);
        }
    }

    static void NormalizeBattleScene()
    {
        var scene = EditorSceneManager.OpenScene(BattleScenePath, OpenSceneMode.Single);
        var battleManager = UnityEngine.Object.FindAnyObjectByType<BattleManager>(FindObjectsInactive.Include);
        if (battleManager == null)
            throw new InvalidOperationException("Battle scene has no BattleManager.");

        var serializedBattle = new SerializedObject(battleManager);
        var playerSpawns = serializedBattle.FindProperty("_heroSpawnTransforms");
        if (playerSpawns == null)
            throw new InvalidOperationException("BattleManager has no _heroSpawnTransforms property.");

        EnsureNinePlayerSpawnTransforms(playerSpawns);

        var activeCount = serializedBattle.FindProperty("_totalActiveHeroesAtATime");
        if (activeCount != null) activeCount.intValue = 5;

        serializedBattle.ApplyModifiedPropertiesWithoutUndo();
        EditorUtility.SetDirty(battleManager);

        var placementGrid = UnityEngine.Object.FindAnyObjectByType<UI_BattlePlacementGrid>(FindObjectsInactive.Include);
        if (placementGrid == null)
            throw new InvalidOperationException("Battle scene has no UI_BattlePlacementGrid.");

        var gridObject = new SerializedObject(placementGrid);
        var blocks = gridObject.FindProperty("_gridBlocksUI");
        if (blocks == null || !blocks.isArray || blocks.arraySize != 9)
            throw new InvalidOperationException($"Battle placement grid must expose exactly 9 slots. Found {blocks?.arraySize ?? 0}.");

        for (int i = 0; i < blocks.arraySize; i++)
        {
            var block = blocks.GetArrayElementAtIndex(i).objectReferenceValue as UI_BattlePlacementGridBlock;
            if (block == null)
                throw new InvalidOperationException($"Battle placement slot {i} is null.");

            block.GridID = i + 1;
            block.gameObject.SetActive(true);
            EditorUtility.SetDirty(block);
        }

        EditorSceneManager.MarkSceneDirty(scene);
        EditorSceneManager.SaveScene(scene);
    }

    static void EnsureNinePlayerSpawnTransforms(SerializedProperty playerSpawns)
    {
        if (playerSpawns.arraySize == 9)
            return;

        if (playerSpawns.arraySize != 6)
            throw new InvalidOperationException($"Expected legacy player spawn count 6 or migrated count 9, found {playerSpawns.arraySize}.");

        var existing = Enumerable.Range(0, 6)
            .Select(i => playerSpawns.GetArrayElementAtIndex(i).objectReferenceValue as Transform)
            .ToArray();

        if (existing.Any(x => x == null))
            throw new InvalidOperationException("Legacy player spawn array contains null transforms.");

        var parent = existing[0].parent;
        if (parent == null)
            throw new InvalidOperationException("Legacy player spawn transforms require a common parent.");

        if (existing.Any(x => x.parent != parent))
            throw new InvalidOperationException("Legacy player spawn transforms do not share a common parent.");

        Vector3 columnA = existing[0].localPosition;
        Vector3 columnB = existing[3].localPosition;
        float nextColumnX = columnB.x + (columnB.x - columnA.x);

        playerSpawns.arraySize = 9;

        for (int row = 0; row < 3; row++)
        {
            int targetIndex = 6 + row;
            var go = new GameObject($"HeroSpawnSlot_{targetIndex + 1}");
            Undo.RegisterCreatedObjectUndo(go, "Create Awakened Realms formation spawn slot");
            go.transform.SetParent(parent, false);

            var rowSource = existing[3 + row];
            var local = rowSource.localPosition;
            local.x = nextColumnX;
            go.transform.localPosition = local;
            go.transform.localRotation = rowSource.localRotation;
            go.transform.localScale = rowSource.localScale;

            playerSpawns.GetArrayElementAtIndex(targetIndex).objectReferenceValue = go.transform;
        }
    }
}
