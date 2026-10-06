using UnityEditor;
using UnityEngine;

namespace AwakenedRealm.EditorTools
{
    /// <summary>
    /// Import rules for curated generated concept art under
    /// Assets/AwakenedRealmsGenerated/Concepts. Only that folder is touched; everything
    /// else is ignored. Rules:
    ///  - backgrounds/world/bosses: Sprite 2D, Android-friendly size/compression, mipmaps
    ///    off, alpha handling chosen per file via the texture's actual alpha content.
    ///  - meta-ui/progression/ui-icons/evolution-auras/enemies/equipment: Sprite 2D, no
    ///    mipmaps, non-readable, tighter max size.
    ///  - vfx/combat-fx: Sprite 2D concept source references, flagged via AssetDatabase
    ///    userData so the catalog builder can mark them RequiresRuntimeRebuild.
    /// </summary>
    public sealed class GeneratedConceptImporter : AssetPostprocessor
    {
        const string ConceptsRoot = "Assets/AwakenedRealmsGenerated/Concepts/";

        // Pixels-per-unit per category: large backgrounds fill the screen, smaller
        // icon/square art is authored at 768px and maps to Unity UI at 100/128.
        const float BackgroundPixelsPerUnit = 100f;
        const float UiPixelsPerUnit = 128f;
        const float ConceptFxPixelsPerUnit = 128f;

        static bool IsConceptPath(string path)
        {
            return !string.IsNullOrEmpty(path) && path.StartsWith(ConceptsRoot, System.StringComparison.Ordinal);
        }

        static string CategoryOf(string path)
        {
            // path = Assets/AwakenedRealmsGenerated/Concepts/<category>/<file>
            var rest = path.Substring(ConceptsRoot.Length);
            var slash = rest.IndexOf('/');
            return slash > 0 ? rest.Substring(0, slash) : rest;
        }

        void OnPreprocessTexture()
        {
            if (!IsConceptPath(assetPath))
            {
                return;
            }

            var importer = (TextureImporter)assetImporter;
            var category = CategoryOf(assetPath);

            // Shared safe defaults for all generated art.
            importer.textureType = TextureImporterType.Sprite;
            importer.spriteImportMode = SpriteImportMode.Single;
            importer.mipmapEnabled = false;
            importer.isReadable = false;
            importer.wrapMode = TextureWrapMode.Clamp;
            importer.npotScale = TextureImporterNPOTScale.None;

            // Per-file alpha handling: detect actual alpha in the source and pick the
            // cheapest correct format path.
            var sourceHasAlpha = importer.DoesSourceTextureHaveAlpha();
            importer.alphaSource = TextureImporterAlphaSource.FromInput;
            importer.alphaIsTransparency = sourceHasAlpha;

            switch (category)
            {
                case "backgrounds":
                case "world":
                    Configure(importer, maxSize: 2048, ppu: BackgroundPixelsPerUnit,
                        filter: FilterMode.Bilinear, compression: TextureImporterCompression.Compressed);
                    break;
                case "bosses":
                    Configure(importer, maxSize: 2048, ppu: BackgroundPixelsPerUnit,
                        filter: FilterMode.Bilinear, compression: TextureImporterCompression.Compressed);
                    break;
                case "meta-ui":
                case "progression":
                case "ui-icons":
                case "evolution-auras":
                case "equipment":
                case "enemies":
                    Configure(importer, maxSize: 1024, ppu: UiPixelsPerUnit,
                        filter: FilterMode.Bilinear, compression: TextureImporterCompression.Compressed);
                    break;
                case "vfx":
                case "combat-fx":
                    // Concept card, not a final runtime effect.
                    Configure(importer, maxSize: 1024, ppu: ConceptFxPixelsPerUnit,
                        filter: FilterMode.Bilinear, compression: TextureImporterCompression.Compressed);
                    importer.userData = "concept-source-reference;requires-runtime-rebuild";
                    break;
                default:
                    Configure(importer, maxSize: 1024, ppu: UiPixelsPerUnit,
                        filter: FilterMode.Bilinear, compression: TextureImporterCompression.Compressed);
                    break;
            }
        }

        static void Configure(TextureImporter importer, int maxSize, float ppu,
            FilterMode filter, TextureImporterCompression compression)
        {
            importer.maxTextureSize = maxSize;
            importer.spritePixelsPerUnit = ppu;
            importer.filterMode = filter;
            importer.textureCompression = compression;

            // Android-friendly platform overrides: cap size and use the default
            // compressed format for the active Android build target.
            var android = importer.GetPlatformTextureSettings("Android");
            android.overridden = true;
            android.maxTextureSize = maxSize;
            android.format = TextureImporterFormat.Automatic;
            android.textureCompression = compression;
            importer.SetPlatformTextureSettings(android);
        }
    }
}
