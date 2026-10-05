#if UNITY_EDITOR
using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace IdleSlime.Editor
{
    public static class AwakenedRealmsAndroidBuild
    {
        public static void BuildReleaseAab()
        {
            Configure();
            var output = Path.GetFullPath($"Builds/Android/AwakenedRealms-{PlayerSettings.bundleVersion}.aab");
            Directory.CreateDirectory(Path.GetDirectoryName(output));
            EditorUserBuildSettings.buildAppBundle = true;
            var scenes = EditorBuildSettings.scenes
                .Where(s => s.enabled && !string.IsNullOrWhiteSpace(s.path))
                .Select(s => s.path).ToArray();
            if (scenes.Length == 0) throw new InvalidOperationException("No enabled build scenes found.");
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
                scenes = scenes,
                locationPathName = output,
                target = BuildTarget.Android,
                options = BuildOptions.None
            });
            if (report.summary.result != BuildResult.Succeeded)
                throw new Exception("Android AAB build failed: " + report.summary.result);
            Debug.Log("AWAKENED_REALMS_AAB=" + output);
        }

        private static void Configure()
        {
            PlayerSettings.companyName = "Nexus Core Inc.";
            PlayerSettings.productName = "Awakened Realms: Idle RPG";
            PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, "com.nexuscoreinc.awakenedrealms");
            var versionName = Environment.GetEnvironmentVariable("AWAKENED_VERSION_NAME");
            if (!string.IsNullOrWhiteSpace(versionName)) PlayerSettings.bundleVersion = versionName;
            var versionCode = Environment.GetEnvironmentVariable("AWAKENED_VERSION_CODE");
            if (!string.IsNullOrWhiteSpace(versionCode)) PlayerSettings.Android.bundleVersionCode = int.Parse(versionCode);
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel25;
            PlayerSettings.Android.targetSdkVersion = (AndroidSdkVersions)36;
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.defaultInterfaceOrientation = UIOrientation.Portrait;

            var ks = Require("AWAKENED_KEYSTORE");
            if (!File.Exists(ks)) throw new FileNotFoundException("Upload keystore not found", ks);
            PlayerSettings.Android.useCustomKeystore = true;
            PlayerSettings.Android.keystoreName = ks;
            PlayerSettings.Android.keystorePass = Require("AWAKENED_KEYSTORE_PASS");
            PlayerSettings.Android.keyaliasName = Require("AWAKENED_KEY_ALIAS");
            PlayerSettings.Android.keyaliasPass = Require("AWAKENED_KEY_ALIAS_PASS");
        }

        private static string Require(string name)
        {
            var value = Environment.GetEnvironmentVariable(name);
            if (string.IsNullOrEmpty(value)) throw new InvalidOperationException("Missing " + name);
            return value;
        }
    }
}
#endif
