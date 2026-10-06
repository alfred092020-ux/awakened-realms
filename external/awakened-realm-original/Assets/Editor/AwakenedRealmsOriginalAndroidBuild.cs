#if UNITY_EDITOR
using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

public static class AwakenedRealmsOriginalAndroidBuild
{
    public static void BuildDevelopmentApk()
    {
        ConfigureCommon();
        PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, "com.nexuscoreinc.awakenedrealms.dev");
        PlayerSettings.Android.useCustomKeystore = false;
        EditorUserBuildSettings.buildAppBundle = false;

        var output = Path.GetFullPath("Builds/Android/AwakenedRealms-Original-Dev.apk");
        Directory.CreateDirectory(Path.GetDirectoryName(output));
        Build(output, BuildOptions.Development);
        Debug.Log("AWAKENED_REALMS_ORIGINAL_DEV_APK=" + output);
    }

    public static void BuildQaSideBySideApk()
    {
        ConfigureCommon();
        PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, "com.nexuscoreinc.awakenedrealms.qa");
        PlayerSettings.Android.useCustomKeystore = false;
        EditorUserBuildSettings.buildAppBundle = false;

        var output = Path.GetFullPath("Builds/Android/AwakenedRealms-QA-SideBySide.apk");
        Directory.CreateDirectory(Path.GetDirectoryName(output));
        Build(output, BuildOptions.Development);
        Debug.Log("AWAKENED_REALMS_QA_SIDEBYSIDE_APK=" + output);
    }

    public static void ConfigureProductionProject()
    {
        ConfigureCommon();
        PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, "com.nexuscoreinc.awakenedrealms");
        Debug.Log("AWAKENED_REALMS_ORIGINAL_PRODUCTION_CONFIGURED");
    }

    static void ConfigureCommon()
    {
        PlayerSettings.companyName = "Nexus Core Inc.";
        PlayerSettings.productName = "Awakened Realms: Idle RPG";
        PlayerSettings.bundleVersion = string.IsNullOrWhiteSpace(PlayerSettings.bundleVersion) ? "1.0.0" : PlayerSettings.bundleVersion;
        if (PlayerSettings.Android.bundleVersionCode < 1) PlayerSettings.Android.bundleVersionCode = 1;

        PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel25;
        PlayerSettings.Android.targetSdkVersion = (AndroidSdkVersions)36;
        PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
        PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.IL2CPP);

        PlayerSettings.defaultInterfaceOrientation = UIOrientation.Portrait;
        PlayerSettings.allowedAutorotateToPortrait = true;
        PlayerSettings.allowedAutorotateToPortraitUpsideDown = false;
        PlayerSettings.allowedAutorotateToLandscapeLeft = false;
        PlayerSettings.allowedAutorotateToLandscapeRight = false;
    }

    static void Build(string output, BuildOptions options)
    {
        var scenes = EditorBuildSettings.scenes
            .Where(scene => scene.enabled && !string.IsNullOrWhiteSpace(scene.path))
            .Select(scene => scene.path)
            .ToArray();

        if (scenes.Length == 0)
            throw new InvalidOperationException("No enabled build scenes found.");

        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
        {
            scenes = scenes,
            locationPathName = output,
            target = BuildTarget.Android,
            options = options
        });

        if (report.summary.result != BuildResult.Succeeded)
            throw new InvalidOperationException("Android build failed: " + report.summary.result);
    }
}
#endif
