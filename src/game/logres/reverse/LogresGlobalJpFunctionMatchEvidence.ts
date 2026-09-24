export const LOGRES_GLOBAL_JP_FUNCTION_MATCH_PROVENANCE =
  'GLOBAL_3_0_24_AUTHORITY_WITH_CURRENT_JP_STRUCTURAL_LINEAGE' as const

export const LOGRES_GLOBAL_JP_FUNCTION_MATCH_SOURCES =
  Object.freeze({
    global3024LibgameSha256:
      'bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f',
    currentJpLibgameSha256:
      '1564f02b23c9909adc0d26636adfc8e72a7ed9363655af0d1ae22635e55acbeb',
    cachedBroaderSymbolDiffSha256:
      '6a55d143312d6c5e44b9c0c95f55c53ed8bf1076cad481ca1c134725a8f3178f',
  } as const)

export const LOGRES_GLOBAL_JP_FUNCTION_MATCH_COUNTS =
  Object.freeze({
    globalDefinedLfsFunctions: 19867,
    currentJpDefinedLfsFunctions: 40077,
    exactSymbolCorrespondences: 16338,
    globalFunctionOnly: 3529,
    currentJpFunctionOnly: 23739,

    exactSymbolNormalizedBodyIdentical: 1584,
    exactSymbolNormalizedBodyChanged: 14753,

    structuralHighResolved: 41,
    structuralMediumResolved: 82,
    unresolvedGlobalFunctions: 3406,

    globalBodyHashes: 19866,
    currentJpBodyHashes: 40077,
    globalWithStringRefs: 3730,
    currentJpWithStringRefs: 8965,
    globalWithDirectCalls: 2531,
    currentJpWithDirectCalls: 20906,

    structuralAmbiguous: 975,
    structuralLowOnly: 1410,
    targetCollisions: 0,

    broaderGlobalLfsSymbolSurface: 20240,
    broaderCurrentJpLfsSymbolSurface: 40709,
    broaderCommonLfsSymbolSurface: 16667,
  } as const)

export const LOGRES_GLOBAL_JP_FUNCTION_MATCH_FEATURES =
  Object.freeze([
    'exact raw demangled lfs:: function symbol',
    'address-independent normalized AArch64 instruction SHA-256',
    'function byte size',
    'ASCII string references recovered from ADR, ADRP and LDR-literal patterns',
    'direct BL call-neighborhood resolved to exact symbols or bounded KnownSymbol+offset neighborhoods',
    'class/method and argument-arity shape',
  ] as const)

export const LOGRES_GLOBAL_JP_FUNCTION_MATCH_HIGH_EXAMPLES =
  Object.freeze([
    Object.freeze({
      global:
        'lfs::FriendInfo::deleteFriend(uidCUID)',
      currentJp:
        'lfs::FriendInfo::deleteFriend(lfs::uid::UIDType<lfs::uid::tag::CUID>)',
      evidence:
        'same class+method, exact normalized instruction body, exact byte size',
    }),
    Object.freeze({
      global:
        'lfs::CharacterStatus::ItemBoxChangeHandlerImpl::onItemAdded(lfs::ItemBox&, std::__ndk1::vector<uidItemUID, std::__ndk1::allocator<uidItemUID> > const&)',
      currentJp:
        'lfs::CharacterStatus::ItemBoxChangeHandlerImpl::onItemAdded(lfs::ItemBox&, std::__ndk1::vector<lfs::uid::UIDType<lfs::uid::tag::ItemUID>, std::__ndk1::allocator<lfs::uid::UIDType<lfs::uid::tag::ItemUID> > > const&)',
      evidence:
        'same class+method, exact normalized instruction body, exact byte size',
    }),
    Object.freeze({
      global:
        'lfs::NetworkSession::C_GMCL_DECLARE_HIRABLE_TO_CLAN_Response(unsigned int, GmClProto::chat_result, std::__ndk1::basic_string<char, std::__ndk1::char_traits<char>, std::__ndk1::allocator<char> >)',
      currentJp:
        'lfs::NetworkSession::C_GMCL_DECLARE_HIRABLE_TO_CLAN_Response(unsigned int, GmClProto::result_t const&, std::__ndk1::basic_string<char, std::__ndk1::char_traits<char>, std::__ndk1::allocator<char> > const&)',
      evidence:
        'same NetworkSession method, exact normalized instruction body, exact byte size',
    }),
  ] as const)

export const LOGRES_GLOBAL_JP_FUNCTION_MATCH_GUARDRAILS =
  Object.freeze([
    'Global 3.0.24 remains the historical authority; current JP is lineage evidence only.',
    'Exact symbol correspondence proves name correspondence only and does not claim behavioral identity.',
    'A matching normalized instruction hash across unrelated classes is insufficient for high-confidence lineage.',
    'STRUCTURAL_HIGH, STRUCTURAL_MEDIUM and STRUCTURAL_LOW are heuristic lineage tiers and are never labeled exact identity or CONFIRMED ORIGINAL.',
    'Low score margins and many-to-one target collisions remain unresolved.',
    'The broader cached lfs:: symbol surface is reported separately from defined ELF FUNC inventory counts.',
  ] as const)

export const LOGRES_GLOBAL_JP_FUNCTION_MATCH_ARTIFACT =
  '/home/ubuntu/logres/artifacts/global-jp-function-match-20260924.json' as const
