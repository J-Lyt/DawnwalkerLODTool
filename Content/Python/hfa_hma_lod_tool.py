import re
import unreal


# ============================================================
# Dawnwalker LOD Tool
# Unreal Engine 5.5.4
#
# Naming convention:
#
#   SK_HFA_Example_Torso_A -> Female / HFA
#
#   SK_HMA_Example_Torso_A -> Male / HMA
#
# If neither HFA nor HMA can be detected:
#
#   YES    = Female (HFA)
#   NO     = Male (HMA)
#   CANCEL = Skip
#
#
# How to use:
#
#   1. Select SkeletalMesh assets in Content Browser
#   2. Right Click on asset > Scripted Asset Actions > Dawnwalker LOD Tool
#
# What the tool does:
#
#   3. Detects HFA/HMA from asset name
#   4. Generates LOD1-LOD3 if missing
#   5. Populates BonesToRemove arrays
#   6. Match screen-size thresholds
#   7. Match MaxBonesPerVertex
#   8. Regenerates previously generated LODs
#   9. Verifies that BonesToRemove arrays survived regeneration
#  10. Saves asset

# ============================================================


# ============================================================
# CONFIGURATION
# ============================================================

POLICY_HFA = "HFA"
POLICY_HMA = "HMA"

TARGET_LOD_COUNT = 4  # LOD0 + LOD1 + LOD2 + LOD3

SCREEN_SIZE_BY_LOD = {
    1: 0.25,
    2: 0.11,
    3: 0.06,
}

MAX_BONES_PER_VERTEX_BY_LOD = {
    1: 8,
    2: 8,
    3: 4,
}

# False: Only LODs that have been auto-generated previously are regenerated
# True : Imported LODs may also be regenerated
REGENERATE_IMPORTED_LODS = False


# If a LODSettings asset is assigned, it may override local LOD configuration
#
# True: Skip meshes that have LODSettings assigned then show a warning
SKIP_MESHES_WITH_SHARED_LOD_SETTINGS = True


# Show a dialog after completion
SHOW_COMPLETION_DIALOG = True


# ============================================================
# LOD1 BonesToRemove (HFA/HMA)
# 173 bones
# ============================================================

LOD1_BASE = """
middle_03_in_l
middle_02_dip_l
middle_03_bulge_l
middle_04_l
middle_02_side_inn_l
middle_02_side_out_l
middle_02_in_l
middle_02_pip_l
middle_02_bulge_l
middle_01_side_inn_l
middle_01_side_out_l
middle_01_palm_l
middle_01_mcp_l
middle_01_bulge_l
middle_01_palmMid_l
middle_metacarpal_slide_l
pinky_03_in_l
pinky_02_dip_l
pinky_03_bulge_l
pinky_04_l
pinky_02_in_l
pinky_02_pip_l
pinky_02_bulge_l
pinky_02_side_out_l
pinky_02_side_inn_l
pinky_01_side_inn_l
pinky_01_side_out_l
pinky_01_palm_l
pinky_01_mcp_l
pinky_01_bulge_l
pinky_01_palmMid_l
pinky_metacarpal_slide_l
ring_03_in_l
ring_02_dip_l
ring_03_bulge_l
ring_04_l
ring_02_in_l
ring_02_pip_l
ring_02_bulge_l
ring_02_side_out_l
ring_02_side_inn_l
ring_01_palm_l
ring_01_mcp_l
ring_01_bulge_l
ring_01_side_out_l
ring_01_side_inn_l
ring_01_palmMid_l
ring_metacarpal_slide_l
thumb_03_pip_l
thumb_03_in_l
thumb_03_side_out_l
thumb_03_side_inn_l
thumb_03_bulge_l
thumb_04_l
thumb_02_mcp_l
thumb_02_in_l
thumb_02_side_out_l
thumb_02_side_inn_l
thumb_02_bulge_l
thumb_01_side_out_l
thumb_01_side_inn_l
index_03_in_l
index_02_dip_l
index_03_bulge_l
index_04_l
index_02_side_inn_l
index_02_side_out_l
index_02_in_l
index_02_pip_l
index_02_bulge_l
index_01_side_out_l
index_01_side_inn_l
index_01_palm_l
index_01_mcp_l
index_01_bulge_l
index_01_palmMid_l
index_metacarpal_slide_l
middle_03_in_r
middle_02_dip_r
middle_03_bulge_r
middle_02_side_inn_r
middle_02_side_out_r
middle_02_in_r
middle_02_pip_r
middle_02_bulge_r
middle_01_side_inn_r
middle_01_side_out_r
middle_01_palm_r
middle_01_mcp_r
middle_01_bulge_r
middle_01_palmMid_r
middle_metacarpal_slide_r
pinky_03_in_r
pinky_02_dip_r
pinky_03_bulge_r
pinky_04_r
pinky_02_in_r
pinky_02_pip_r
pinky_02_bulge_r
pinky_02_side_out_r
pinky_02_side_inn_r
pinky_01_side_inn_r
pinky_01_side_out_r
pinky_01_palm_r
pinky_01_mcp_r
pinky_01_bulge_r
pinky_01_palmMid_r
pinky_metacarpal_slide_r
ring_03_in_r
ring_02_dip_r
ring_03_bulge_r
ring_04_r
ring_02_in_r
ring_02_pip_r
ring_02_bulge_r
ring_02_side_out_r
ring_02_side_inn_r
ring_01_palm_r
ring_01_mcp_r
ring_01_bulge_r
ring_01_side_out_r
ring_01_side_inn_r
ring_01_palmMid_r
ring_metacarpal_slide_r
thumb_03_pip_r
thumb_03_in_r
thumb_03_side_out_r
thumb_03_side_inn_r
thumb_03_bulge_r
thumb_04_r
thumb_02_mcp_r
thumb_02_in_r
thumb_02_side_out_r
thumb_02_side_inn_r
thumb_02_bulge_r
thumb_01_side_out_r
thumb_01_side_inn_r
index_03_in_r
index_02_dip_r
index_03_bulge_r
index_04_r
index_02_side_inn_r
index_02_side_out_r
index_02_in_r
index_02_pip_r
index_02_bulge_r
index_01_side_out_r
index_01_side_inn_r
index_01_palm_r
index_01_mcp_r
index_01_bulge_r
index_01_palmMid_r
index_metacarpal_slide_r
indextoe_01_r
indextoe_02_r
bigtoe_01_r
bigtoe_02_r
littletoe_01_r
littletoe_02_r
middletoe_01_r
middletoe_02_r
ringtoe_01_r
ringtoe_02_r
indextoe_01_l
indextoe_02_l
bigtoe_01_l
bigtoe_02_l
ringtoe_01_l
ringtoe_02_l
middletoe_01_l
middletoe_02_l
littletoe_01_l
littletoe_02_l
""".split()


# ============================================================
# LOD2 BonesToRemove (HFA/HMA)
# 90 bones
#
# Total = 263 bones
# ============================================================

LOD2_ADDITIONAL = """
lowerarm_in_l
lowerarm_out_l
lowerarm_fwd_l
lowerarm_bck_l
middle_03_half_l
middle_02_half_l
middle_01_half_l
pinky_03_half_l
pinky_02_half_l
pinky_01_half_l
ring_03_half_l
ring_02_half_l
ring_01_half_l
thumb_03_half_l
thumb_02_half_l
index_03_half_l
index_02_half_l
index_01_half_l
wrist_inner_l
wrist_outer_l
upperarm_twistCor_01_l
upperarm_tricep_l
upperarm_bicep_l
upperarm_twistCor_02_l
upperarm_bck_l
upperarm_fwd_l
upperarm_in_l
upperarm_out_l
clavicle_out_l
clavicle_scap_l
lowerarm_out_r
lowerarm_in_r
lowerarm_fwd_r
lowerarm_bck_r
middle_03_half_r
middle_02_half_r
middle_01_half_r
pinky_03_half_r
pinky_02_half_r
pinky_01_half_r
ring_03_half_r
ring_02_half_r
ring_01_half_r
thumb_03_half_r
thumb_02_half_r
index_03_half_r
index_02_half_r
index_01_half_r
wrist_inner_r
wrist_outer_r
upperarm_twistCor_01_r
upperarm_tricep_r
upperarm_bicep_r
upperarm_twistCor_02_r
upperarm_bck_r
upperarm_in_r
upperarm_fwd_r
upperarm_out_r
clavicle_out_r
clavicle_scap_r
clavicle_pec_r
spine_04_latissimus_l
spine_04_latissimus_r
clavicle_pec_l
ankle_bck_r
ankle_fwd_r
calf_twistCor_02_r
calf_kneeBack_r
calf_knee_r
thigh_twistCor_01_r
thigh_twistCor_02_r
thigh_fwd_r
thigh_bck_r
thigh_out_r
thigh_in_r
thigh_bck_lwr_r
thigh_fwd_lwr_r
ankle_bck_l
ankle_fwd_l
calf_twistCor_02_l
calf_kneeBack_l
calf_knee_l
thigh_twistCor_01_l
thigh_twistCor_02_l
thigh_bck_l
thigh_fwd_l
thigh_out_l
thigh_bck_lwr_l
thigh_in_l
thigh_fwd_lwr_l
""".split()


# ============================================================
# LOD3 BonesToRemove (HFA/HMA)
# 46 bones
#
# Total = 309 bones
# ============================================================

LOD3_ADDITIONAL = """
lowerarm_twist_02_l
lowerarm_twist_01_l
pinky_metacarpal_l
pinky_01_l
pinky_02_l
pinky_03_l
ring_metacarpal_l
ring_01_l
ring_02_l
ring_03_l
index_metacarpal_l
index_01_l
index_02_l
index_03_l
upperarm_twist_01_l
upperarm_twist_02_l
upperarm_correctiveRoot_l
lowerarm_twist_02_r
lowerarm_twist_01_r
pinky_metacarpal_r
pinky_01_r
pinky_02_r
pinky_03_r
ring_metacarpal_r
ring_01_r
ring_02_r
ring_03_r
index_metacarpal_r
index_01_r
index_02_r
index_03_r
upperarm_twist_01_r
upperarm_twist_02_r
upperarm_correctiveRoot_r
calf_twist_02_r
calf_twist_01_r
calf_correctiveRoot_r
thigh_twist_01_r
thigh_twist_02_r
thigh_correctiveRoot_r
calf_twist_02_l
calf_twist_01_l
calf_correctiveRoot_l
thigh_twist_01_l
thigh_twist_02_l
thigh_correctiveRoot_l
""".split()


# ============================================================
# LOD3 BonesToRemove (HMA)
#
# HMA is identical to HFA at LOD1 and LOD2
# HMA has 11 additional BonesToRemove at LOD3
#
# Total = 320 bones
# ============================================================

HMA_LOD3_ADDITIONAL = """
belly_01
belly_02
belly_03
clavicle_in_l
clavicle_in_r
clavicle_sternum_l
clavicle_sternum_r
calf_l_untwist
calf_r_untwist
thigh_l_untwist
thigh_r_untwist
""".split()


# ============================================================
# BUILD POLICIES
# ============================================================

HFA_BONES_TO_REMOVE_BY_LOD = {
    1: list(
        LOD1_BASE
    ),

    2: list(
        LOD1_BASE
        + LOD2_ADDITIONAL
    ),

    3: list(
        LOD1_BASE
        + LOD2_ADDITIONAL
        + LOD3_ADDITIONAL
    ),
}


HMA_BONES_TO_REMOVE_BY_LOD = {
    1: list(
        LOD1_BASE
    ),

    2: list(
        LOD1_BASE
        + LOD2_ADDITIONAL
    ),

    3: list(
        LOD1_BASE
        + LOD2_ADDITIONAL
        + LOD3_ADDITIONAL
        + HMA_LOD3_ADDITIONAL
    ),
}


BONE_POLICIES = {
    POLICY_HFA: HFA_BONES_TO_REMOVE_BY_LOD,
    POLICY_HMA: HMA_BONES_TO_REMOVE_BY_LOD,
}


EXPECTED_BONE_COUNTS = {
    POLICY_HFA: {
        1: 173,
        2: 263,
        3: 309,
    },

    POLICY_HMA: {
        1: 173,
        2: 263,
        3: 320,
    },
}


# ============================================================
# POLICY SANITY CHECKS
# ============================================================

for policy_name, expected_lods in EXPECTED_BONE_COUNTS.items():

    policy = BONE_POLICIES[
        policy_name
    ]

    for lod_index, expected_count in expected_lods.items():

        actual_count = len(
            policy[lod_index]
        )

        if actual_count != expected_count:

            raise RuntimeError(
                (
                    "Internal policy error: "
                    "{} LOD{} contains {} bones; "
                    "expected {}."
                ).format(
                    policy_name,
                    lod_index,
                    actual_count,
                    expected_count
                )
            )


# ============================================================
# LOGGING
# ============================================================

LOG_PREFIX = "[Dawnwalker LOD Tool]"


def log(message):

    unreal.log(
        "{} {}".format(
            LOG_PREFIX,
            message
        )
    )


def warn(message):

    unreal.log_warning(
        "{} {}".format(
            LOG_PREFIX,
            message
        )
    )


def error(message):

    unreal.log_error(
        "{} {}".format(
            LOG_PREFIX,
            message
        )
    )


# ============================================================
# POLICY DETECTION
# ============================================================

def asset_name_contains_token(
    asset_name,
    token
):
    """
    Matches HFA / HMA as a distinct naming token.

    Matches:
        SK_HFA_Example_Torso_A
        HFA_Example
        Example-HFA-Test

    Does not intentionally match the letters as part of
    a longer alphanumeric word.
    """

    pattern = (
        r"(^|[^A-Za-z0-9])"
        + re.escape(token)
        + r"([^A-Za-z0-9]|$)"
    )

    return (
        re.search(
            pattern,
            asset_name,
            flags=re.IGNORECASE
        )
        is not None
    )


def prompt_for_policy(mesh):
    """
    Fallback if automatic HFA/HMA detection fails.

    YES    = Female / HFA
    NO     = Male / HMA
    CANCEL = Skip
    """

    result = (
        unreal.EditorDialog.show_message(
            "Select Skeleton",

            (
                "Could not automatically detect "
                "the skeleton for:\n\n"
                "{}\n\n"
                "YES = Female (HFA)\n"
                "NO = Male (HMA)\n"
                "CANCEL = Skip this mesh"
            ).format(
                mesh.get_name()
            ),

            unreal.AppMsgType.YES_NO_CANCEL,

            unreal.AppReturnType.CANCEL
        )
    )

    if result == unreal.AppReturnType.YES:

        return POLICY_HFA

    if result == unreal.AppReturnType.NO:

        return POLICY_HMA

    return None


def detect_policy(mesh):
    """
    Detection order:

        HFA only -> HFA
        HMA only -> HMA
        neither  -> prompt
        both     -> prompt
    """

    asset_name = mesh.get_name()

    has_hfa = asset_name_contains_token(
        asset_name,
        POLICY_HFA
    )

    has_hma = asset_name_contains_token(
        asset_name,
        POLICY_HMA
    )

    if has_hfa and not has_hma:

        log(
            "{}: automatically detected "
            "Female (HFA).".format(
                asset_name
            )
        )

        return POLICY_HFA

    if has_hma and not has_hfa:

        log(
            "{}: automatically detected "
            "Male (HMA).".format(
                asset_name
            )
        )

        return POLICY_HMA

    if has_hfa and has_hma:

        warn(
            "{}: name contains both HFA "
            "and HMA; prompting user."
            .format(
                asset_name
            )
        )

    else:

        warn(
            "{}: no HFA/HMA token found; "
            "prompting user."
            .format(
                asset_name
            )
        )

    return prompt_for_policy(
        mesh
    )


# ============================================================
# BONE REFERENCE CREATION
# ============================================================

def make_bone_references(
    bone_names
):
    """
    Convert strings to Unreal FBoneReference structs.
    """

    bone_refs = []

    for bone_name in bone_names:

        reference = unreal.BoneReference()

        reference.set_editor_property(
            "bone_name",
            unreal.Name(
                bone_name
            )
        )

        bone_refs.append(
            reference
        )

    return bone_refs


# ============================================================
# LOD HELPERS
# ============================================================

def get_lod_count(mesh):

    return (
        unreal.SkeletalMeshEditorSubsystem
        .get_lod_count(
            mesh
        )
    )


def ensure_required_lods(mesh):
    """
    Ensure LOD0-LOD3 exist.

    Existing LODs are retained.

    If fewer than four exist, Unreal generates the
    missing LODs.
    """

    current_count = get_lod_count(
        mesh
    )

    if current_count >= TARGET_LOD_COUNT:

        log(
            "{}: already has {} LOD(s)."
            .format(
                mesh.get_name(),
                current_count
            )
        )

        if current_count > TARGET_LOD_COUNT:

            warn(
                "{}: has {} LODs. "
                "This tool only manages LOD1-LOD3."
                .format(
                    mesh.get_name(),
                    current_count
                )
            )

        return True

    log(
        "{}: generating missing LODs "
        "({} -> {})."
        .format(
            mesh.get_name(),
            current_count,
            TARGET_LOD_COUNT
        )
    )

    success = (
        unreal.SkeletalMeshEditorSubsystem
        .regenerate_lod(
            mesh,
            TARGET_LOD_COUNT,
            REGENERATE_IMPORTED_LODS,
            False
        )
    )

    if not success:

        error(
            "{}: failed to generate "
            "LOD1-LOD3."
            .format(
                mesh.get_name()
            )
        )

        return False

    new_count = get_lod_count(
        mesh
    )

    if new_count < TARGET_LOD_COUNT:

        error(
            "{}: expected {} LODs, "
            "but Unreal reports {}."
            .format(
                mesh.get_name(),
                TARGET_LOD_COUNT,
                new_count
            )
        )

        return False

    return True


# ============================================================
# APPLY POLICY
# ============================================================

def apply_policy_to_lod_info_array(
    mesh,
    policy_name
):
    """
    Apply BonesToRemove and matching skeletal reduction settings.
    """

    bones_to_remove_by_lod = (
        BONE_POLICIES[
            policy_name
        ]
    )

    lod_infos = list(
        mesh.get_editor_property(
            "lod_info"
        )
    )

    if len(lod_infos) < TARGET_LOD_COUNT:

        raise RuntimeError(
            (
                "{} has only {} LODInfo entries; "
                "{} are required."
            ).format(
                mesh.get_name(),
                len(lod_infos),
                TARGET_LOD_COUNT
            )
        )

    for lod_index in (
        1,
        2,
        3
    ):

        lod_info = (
            lod_infos[
                lod_index
            ]
        )

        # ----------------------------------------------------
        # Bones To Remove
        # ----------------------------------------------------

        bone_names = (
            bones_to_remove_by_lod[
                lod_index
            ]
        )

        bone_refs = (
            make_bone_references(
                bone_names
            )
        )

        lod_info.set_editor_property(
            "bones_to_remove",
            bone_refs
        )

        # ----------------------------------------------------
        # Screen Size
        # ----------------------------------------------------

        lod_info.set_editor_property(
            "screen_size",

            unreal.PerPlatformFloat(
                default=(
                    SCREEN_SIZE_BY_LOD[
                        lod_index
                    ]
                )
            )
        )

        # ----------------------------------------------------
        # Reduction Settings
        #
        # We deliberately DO NOT copy the leader's
        # extreme geometry limits:
        #
        #     MaxNumOfTriangles = 4
        #     MaxNumOfVerts = 6
        #
        # Those are unsuitable for visible clothing.
        # ----------------------------------------------------

        reduction = (
            lod_info.get_editor_property(
                "reduction_settings"
            )
        )

        reduction.set_editor_property(
            "base_lod",
            0
        )

        reduction.set_editor_property(
            "max_bones_per_vertex",
            MAX_BONES_PER_VERTEX_BY_LOD[
                lod_index
            ]
        )

        reduction.set_editor_property(
            "improve_triangles_for_cloth",
            True
        )

        # Nested struct:
        # explicitly assign it back.
        lod_info.set_editor_property(
            "reduction_settings",
            reduction
        )

        # CRITICAL UE 5.5 FIX:
        # explicitly place the modified struct
        # back into the array.
        lod_infos[
            lod_index
        ] = lod_info

        log(
            (
                "{} LOD{}: {} policy, "
                "{} BonesToRemove, "
                "ScreenSize={}, "
                "MaxBonesPerVertex={}"
            ).format(
                mesh.get_name(),
                lod_index,
                policy_name,
                len(bone_refs),
                SCREEN_SIZE_BY_LOD[
                    lod_index
                ],
                MAX_BONES_PER_VERTEX_BY_LOD[
                    lod_index
                ]
            )
        )

    # CRITICAL UE 5.5 FIX:
    # assign the entire struct array back.
    mesh.set_editor_property(
        "lod_info",
        lod_infos
    )


# ============================================================
# VERIFICATION
# ============================================================

def verify_bones_to_remove(
    mesh,
    policy_name,
    lod_index,
    stage
):
    """
    Re-read the SkeletalMesh asset and confirm that
    Unreal actually stored the expected array.
    """

    expected_names = (
        BONE_POLICIES[
            policy_name
        ][
            lod_index
        ]
    )

    fresh_lod_infos = list(
        mesh.get_editor_property(
            "lod_info"
        )
    )

    if lod_index >= len(
        fresh_lod_infos
    ):

        error(
            "{}: {} verification failed; "
            "LOD{} does not exist."
            .format(
                mesh.get_name(),
                stage,
                lod_index
            )
        )

        return False

    stored_refs = list(
        fresh_lod_infos[
            lod_index
        ].get_editor_property(
            "bones_to_remove"
        )
    )

    stored_names = [
        str(
            reference.get_editor_property(
                "bone_name"
            )
        )
        for reference in stored_refs
    ]

    if stored_names != expected_names:

        expected_set = set(
            expected_names
        )

        stored_set = set(
            stored_names
        )

        missing = [
            name
            for name in expected_names
            if name not in stored_set
        ]

        unexpected = [
            name
            for name in stored_names
            if name not in expected_set
        ]

        error(
            (
                "{} LOD{}: {} verification "
                "FAILED. Stored={}, "
                "Expected={}, Missing={}, "
                "Unexpected={}"
            ).format(
                mesh.get_name(),
                lod_index,
                stage,
                len(stored_names),
                len(expected_names),
                len(missing),
                len(unexpected)
            )
        )

        if missing:

            error(
                "Missing sample: {}".format(
                    ", ".join(
                        missing[:12]
                    )
                )
            )

        if unexpected:

            error(
                "Unexpected sample: {}".format(
                    ", ".join(
                        unexpected[:12]
                    )
                )
            )

        return False

    log(
        (
            "{} LOD{}: {} verification OK "
            "({} {}, {} bones)."
        ).format(
            mesh.get_name(),
            lod_index,
            stage,
            policy_name,
            lod_index,
            len(stored_names)
        )
    )

    return True


def verify_all_lods(
    mesh,
    policy_name,
    stage
):

    success = True

    for lod_index in (
        1,
        2,
        3
    ):

        if not verify_bones_to_remove(
            mesh,
            policy_name,
            lod_index,
            stage
        ):

            success = False

    return success


# ============================================================
# RESULT TYPES
# ============================================================

RESULT_SUCCESS = "success"
RESULT_FAILED = "failed"
RESULT_SKIPPED = "skipped"


# ============================================================
# PROCESS ONE MESH
# ============================================================

def process_mesh(mesh):

    asset_name = (
        mesh.get_name()
    )

    log(
        "=" * 72
    )

    log(
        "Processing {}".format(
            asset_name
        )
    )

    # --------------------------------------------------------
    # 1. Detect Female / Male policy
    # --------------------------------------------------------

    policy_name = detect_policy(
        mesh
    )

    if policy_name is None:

        warn(
            "{}: skipped; no policy selected."
            .format(
                asset_name
            )
        )

        return RESULT_SKIPPED

    log(
        "{}: using {} policy."
        .format(
            asset_name,
            policy_name
        )
    )

    # --------------------------------------------------------
    # 2. Check for shared LOD settings
    # --------------------------------------------------------

    shared_lod_settings = (
        mesh.get_editor_property(
            "lod_settings"
        )
    )

    if (
        shared_lod_settings
        and
        SKIP_MESHES_WITH_SHARED_LOD_SETTINGS
    ):

        warn(
            (
                "{}: shared "
                "SkeletalMesh LODSettings '{}' "
                "is assigned. Skipping because "
                "it may override the local "
                "LOD configuration."
            ).format(
                asset_name,
                shared_lod_settings.get_name()
            )
        )

        return RESULT_SKIPPED

    # Mark asset modified / dirty.
    mesh.modify(
        True
    )

    # --------------------------------------------------------
    # 3. Generate missing LOD1-LOD3
    # --------------------------------------------------------

    if not ensure_required_lods(
        mesh
    ):

        return RESULT_FAILED

    # --------------------------------------------------------
    # 4. Apply policy
    # --------------------------------------------------------

    apply_policy_to_lod_info_array(
        mesh,
        policy_name
    )

    # --------------------------------------------------------
    # 5. Verify immediately after writing
    #
    # If this fails, the struct-array assignment has
    # not persisted, so do not regenerate anything.
    # --------------------------------------------------------

    if not verify_all_lods(
        mesh,
        policy_name,
        "PRE-REGEN"
    ):

        error(
            (
                "{}: BonesToRemove did not "
                "persist before regeneration."
            ).format(
                asset_name
            )
        )

        return RESULT_FAILED

    # --------------------------------------------------------
    # 6. Save checkpoint
    # --------------------------------------------------------

    if not (
        unreal.EditorAssetLibrary
        .save_loaded_asset(
            mesh,
            False
        )
    ):

        error(
            "{}: failed to save "
            "pre-regeneration state."
            .format(
                asset_name
            )
        )

        return RESULT_FAILED

    # --------------------------------------------------------
    # 7. Regenerate generated LODs
    #
    # new_lod_count = 0:
    # keep current number of LODs.
    #
    # generate_base_lod = False:
    # leave LOD0 untouched.
    # --------------------------------------------------------

    log(
        "{}: regenerating generated LODs..."
        .format(
            asset_name
        )
    )

    regeneration_success = (
        unreal.SkeletalMeshEditorSubsystem
        .regenerate_lod(
            mesh,
            0,
            REGENERATE_IMPORTED_LODS,
            False
        )
    )

    if not regeneration_success:

        error(
            "{}: LOD regeneration failed."
            .format(
                asset_name
            )
        )

        return RESULT_FAILED

    # --------------------------------------------------------
    # 8. Verify regeneration didn't clear the arrays
    # --------------------------------------------------------

    if not verify_all_lods(
        mesh,
        policy_name,
        "POST-REGEN"
    ):

        error(
            (
                "{}: regeneration changed "
                "or cleared BonesToRemove."
            ).format(
                asset_name
            )
        )

        return RESULT_FAILED

    # --------------------------------------------------------
    # 9. Final save
    # --------------------------------------------------------

    if not (
        unreal.EditorAssetLibrary
        .save_loaded_asset(
            mesh,
            False
        )
    ):

        error(
            "{}: final save failed."
            .format(
                asset_name
            )
        )

        return RESULT_FAILED

    log(
        "{}: COMPLETE ({})"
        .format(
            asset_name,
            policy_name
        )
    )

    return RESULT_SUCCESS


# ============================================================
# COMPLETION DIALOG
# ============================================================

def show_completion_dialog(
    succeeded,
    failed,
    skipped
):

    if not SHOW_COMPLETION_DIALOG:

        return

    lines = [
        "LOD processing complete.",
        "",
        "Succeeded: {}".format(
            len(succeeded)
        ),
        "Failed: {}".format(
            len(failed)
        ),
        "Skipped: {}".format(
            len(skipped)
        ),
    ]

    if failed:

        lines.extend(
            [
                "",
                "Failed assets:",
            ]
        )

        lines.extend(
            failed
        )

    if skipped:

        lines.extend(
            [
                "",
                "Skipped assets:",
            ]
        )

        lines.extend(
            skipped
        )

    unreal.EditorDialog.show_message(
        "Dawnwalker LOD Tool",
        "\n".join(
            lines
        ),
        unreal.AppMsgType.OK,
        unreal.AppReturnType.OK
    )


# ============================================================
# PUBLIC ENTRY POINT
#
# This is the function called by the Editor Utility Widget.
# Importing this module does NOT automatically process assets.
# ============================================================

def run():

    selected_assets = (
        unreal.EditorUtilityLibrary
        .get_selected_assets()
    )

    skeletal_meshes = [
        asset
        for asset in selected_assets
        if isinstance(
            asset,
            unreal.SkeletalMesh
        )
    ]

    if not skeletal_meshes:

        unreal.EditorDialog.show_message(
            "Dawnwalker LOD Tool",

            (
                "Select one or more SkeletalMesh "
                "assets in the Content Browser, "
                "then run the tool again."
            ),

            unreal.AppMsgType.OK,

            unreal.AppReturnType.OK
        )

        return

    succeeded = []
    failed = []
    skipped = []

    log(
        "Selected {} SkeletalMesh asset(s)."
        .format(
            len(skeletal_meshes)
        )
    )

    with unreal.ScopedSlowTask(
        len(skeletal_meshes),
        "Applying LOD policies..."
    ) as task:

        task.make_dialog(
            True
        )

        for mesh in skeletal_meshes:

            if task.should_cancel():

                warn(
                    "Operation cancelled by user."
                )

                break

            task.enter_progress_frame(
                1,

                "Processing {}".format(
                    mesh.get_name()
                )
            )

            try:

                with unreal.ScopedEditorTransaction(
                    "Apply LOD Policy"
                ):

                    result = process_mesh(
                        mesh
                    )

                if result == RESULT_SUCCESS:

                    succeeded.append(
                        mesh.get_name()
                    )

                elif result == RESULT_SKIPPED:

                    skipped.append(
                        mesh.get_name()
                    )

                else:

                    failed.append(
                        mesh.get_name()
                    )

            except Exception as exc:

                failed.append(
                    mesh.get_name()
                )

                error(
                    (
                        "{}: unexpected exception:\n{}"
                    ).format(
                        mesh.get_name(),
                        exc
                    )
                )

    # --------------------------------------------------------
    # Log summary
    # --------------------------------------------------------

    log(
        "=" * 72
    )

    log(
        (
            "Finished. "
            "{} succeeded, "
            "{} failed, "
            "{} skipped."
        ).format(
            len(succeeded),
            len(failed),
            len(skipped)
        )
    )

    if succeeded:

        log(
            "Succeeded: {}".format(
                ", ".join(
                    succeeded
                )
            )
        )

    if failed:

        error(
            "Failed: {}".format(
                ", ".join(
                    failed
                )
            )
        )

    if skipped:

        warn(
            "Skipped: {}".format(
                ", ".join(
                    skipped
                )
            )
        )

    show_completion_dialog(
        succeeded,
        failed,
        skipped
    )