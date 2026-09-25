import json
import math
from pathlib import Path
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
# Policies and aliases: dawnwalker_lod_policies.json
#
# Unknown/ambiguous names prompt for a policy:
#   YES = Use shown policy, NO = Next policy, CANCEL = Skip
# HFA/HMA-only ambiguity retains YES = HFA, NO = HMA, CANCEL = Skip
#
#
# How to use:
#
#   1. Select SkeletalMesh assets in Content Browser
#   2. Right Click on asset > Scripted Asset Actions > Dawnwalker LOD Tool
#
# What the tool does:
#
#   3. Detects the skeleton policy from asset name
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

# Geometry targets are relative to LOD0 (base_lod = 0)
# Explicit targets keep repeated runs from shifting reduction again
GEOMETRY_RETENTION_BY_LOD = {
    0: 1.0,  # Used only when a policy explicitly rebuilds the base LOD
    1: 1.0,
    2: 0.5,
    3: 0.25,
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
# EXTERNAL POLICY DATA
# ============================================================

POLICY_FILE = Path(__file__).with_name("dawnwalker_lod_policies.json")


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: {}".format(key))
        result[key] = value
    return result


def validate_policy_data(data):
    """Expand shared incremental groups before any assets can be modified."""
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported policy schema version")
    groups = data["bone_groups"]
    policies = data["policies"]
    if not isinstance(groups, dict) or not isinstance(policies, dict) or not policies:
        raise ValueError("Expected bone_groups and nonempty policies objects")
    for group_name, names in groups.items():
        if not isinstance(names, list) or any(
            not isinstance(name, str) or not name or name.strip() != name
            for name in names
        ):
            raise ValueError("Invalid bone names in {}".format(group_name))
        if len({name.casefold() for name in names}) != len(names):
            raise ValueError("Duplicate bones in {}".format(group_name))

    expanded = {}
    aliases_seen = set()
    for policy_name, settings in policies.items():
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", policy_name):
            raise ValueError("Invalid policy name: {}".format(policy_name))
        if not isinstance(settings["label"], str) or not settings["label"]:
            raise ValueError("Missing label for {}".format(policy_name))
        aliases = settings["aliases"]
        if not isinstance(aliases, list) or policy_name not in aliases:
            raise ValueError("Policy must include its own name as an alias")
        for alias in aliases:
            if not isinstance(alias, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", alias):
                raise ValueError("Invalid alias for {}".format(policy_name))
            if alias.casefold() in aliases_seen:
                raise ValueError("Duplicate policy alias: {}".format(alias))
            aliases_seen.add(alias.casefold())

        for field in ("additional_bone_groups_by_lod", "expected_counts",
                      "screen_sizes", "max_bones_per_vertex"):
            if not isinstance(settings[field], list) or len(settings[field]) != TARGET_LOD_COUNT:
                raise ValueError("{} {} must contain four LODs".format(policy_name, field))
        if type(settings["regenerate_base_lod"]) is not bool:
            raise ValueError("regenerate_base_lod must be a boolean")

        names = []
        expanded[policy_name] = {}
        previous_screen = float("inf")
        for lod_index in range(TARGET_LOD_COUNT):
            refs = settings["additional_bone_groups_by_lod"][lod_index]
            if not isinstance(refs, list):
                raise ValueError("Bone group references must be lists")
            for ref in refs:
                if not isinstance(ref, str) or ref not in groups:
                    raise ValueError("Unknown bone group: {}".format(ref))
                names.extend(groups[ref])
            if len({name.casefold() for name in names}) != len(names):
                raise ValueError("{} LOD{} has duplicate bones".format(policy_name, lod_index))
            expected = settings["expected_counts"][lod_index]
            if type(expected) is not int or expected < 0 or len(names) != expected:
                raise ValueError("{} LOD{}: {} bones; expected {}".format(
                    policy_name, lod_index, len(names), expected))
            screen = settings["screen_sizes"][lod_index]
            if type(screen) not in (int, float) or not math.isfinite(screen) or not 0 < screen <= previous_screen:
                raise ValueError("Invalid screen sizes for {}".format(policy_name))
            previous_screen = screen
            influences = settings["max_bones_per_vertex"][lod_index]
            if type(influences) is not int or not 1 <= influences <= 12:
                raise ValueError("Invalid influence limit for {}".format(policy_name))
            # Cumulative expansion guarantees that each LOD is a superset
            expanded[policy_name][lod_index] = list(names)
        if bool(expanded[policy_name][0]) != settings["regenerate_base_lod"]:
            raise ValueError("{}: LOD0 removals require base regeneration".format(policy_name))
    return expanded, policies


def load_policy_data(path=POLICY_FILE):
    try:
        with open(path, encoding="utf-8") as policy_file:
            data = json.load(policy_file, object_pairs_hook=_unique_json_object)
        return validate_policy_data(data)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise RuntimeError("Invalid LOD policy file '{}': {}".format(path, exc)) from exc


# Re-read JSON on importlib.reload(), just like the existing Blueprint launcher
BONE_POLICIES, POLICY_SETTINGS = load_policy_data()
EXPECTED_BONE_COUNTS = {
    name: dict(enumerate(settings["expected_counts"]))
    for name, settings in POLICY_SETTINGS.items()
}


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

def matching_policies(asset_name):
    """Match distinct aliases, preferring a compound token at the same location."""
    matches = []
    for policy_name, settings in POLICY_SETTINGS.items():
        for alias in settings["aliases"]:
            pattern = r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])"
            for match in re.finditer(pattern, asset_name, re.IGNORECASE):
                matches.append((match.start(), match.end(), policy_name))
    # BREFIN_B is one policy token, not an ambiguity with BREFIN
    # Separate tokens elsewhere in the name still cause a real ambiguity
    found = {
        name for start, end, name in matches
        if not any(other_start <= start and end <= other_end
                   and (other_start, other_end) != (start, end)
                   for other_start, other_end, _ in matches)
    }
    return [name for name in POLICY_SETTINGS if name in found]


def prompt_for_policy(mesh, candidates=None):
    """Offer matching families, or all families for an unidentified asset."""
    choices = candidates or list(POLICY_SETTINGS)
    if set(choices) == {POLICY_HFA, POLICY_HMA}:
        # Preserve the existing human-only ambiguity dialog
        result = unreal.EditorDialog.show_message(
            "Select Skeleton",
            "Select the skeleton for: {}\n\n"
            "YES = Female (HFA)\nNO = Male (HMA)\nCANCEL = Skip this mesh".format(mesh.get_name()),
            unreal.AppMsgType.YES_NO_CANCEL,
            unreal.AppReturnType.CANCEL
        )
        if result == unreal.AppReturnType.YES:
            return POLICY_HFA
        if result == unreal.AppReturnType.NO:
            return POLICY_HMA
        return None

    for index, policy_name in enumerate(choices):
        result = unreal.EditorDialog.show_message(
            "Select Skeleton ({}/{})".format(index + 1, len(choices)),
            "Asset: {}\n\nUse {} ({})?\n\n"
            "YES = Use this policy\nNO = {}\nCANCEL = Skip this mesh".format(
                mesh.get_name(), POLICY_SETTINGS[policy_name]["label"], policy_name,
                "Next policy" if index + 1 < len(choices) else "Skip this mesh"
            ),
            unreal.AppMsgType.YES_NO_CANCEL,
            unreal.AppReturnType.CANCEL
        )
        if result == unreal.AppReturnType.YES:
            return policy_name
        if result != unreal.AppReturnType.NO:
            return None
    return None


def detect_policy(mesh):
    candidates = matching_policies(mesh.get_name())
    if len(candidates) == 1:
        policy_name = candidates[0]
        log("{}: automatically detected {} ({}).".format(
            mesh.get_name(), POLICY_SETTINGS[policy_name]["label"], policy_name))
        return policy_name
    warn("{}: {} policy tokens; prompting user.".format(
        mesh.get_name(), ", ".join(candidates) if candidates else "no recognized"))
    return prompt_for_policy(mesh, candidates)


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
                "This tool configures LOD0-LOD3."
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

    settings = POLICY_SETTINGS[policy_name]
    screen_sizes = settings["screen_sizes"]
    influence_limits = settings["max_bones_per_vertex"]

    for lod_index in range(TARGET_LOD_COUNT):

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
                    screen_sizes[
                        lod_index
                    ]
                )
            )
        )

        if lod_index == 0 and not settings["regenerate_base_lod"]:
            # Preserve ordinary LOD0 geometry and reduction settings
            lod_infos[lod_index] = lod_info
            continue

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

        # Geometry reduction is independent of each LOD's bone policy
        geometry_retention = GEOMETRY_RETENTION_BY_LOD[lod_index]

        reduction.set_editor_property(
            "termination_criterion",
            unreal.SkeletalMeshTerminationCriterion.SMTC_NUM_OF_TRIANGLES
        )

        reduction.set_editor_property(
            "reduction_method",
            unreal.SkeletalMeshOptimizationType.SMOT_NUM_OF_TRIANGLES
        )

        reduction.set_editor_property(
            "num_of_triangles_percentage",
            geometry_retention
        )

        reduction.set_editor_property(
            "num_of_vert_percentage",
            geometry_retention
        )

        # Percentage criteria also have absolute count caps
        # Use the uint32 maximum so old caps cannot override the targets
        reduction.set_editor_property(
            "max_num_of_triangles_percentage",
            0xFFFFFFFF
        )

        reduction.set_editor_property(
            "max_num_of_verts_percentage",
            0xFFFFFFFF
        )

        log(
            "{} LOD{}: configured to retain {:g}% of LOD0 triangles "
            "when regenerated.".format(
                mesh.get_name(),
                lod_index,
                geometry_retention * 100
            )
        )

        reduction.set_editor_property(
            "max_bones_per_vertex",
            influence_limits[
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
                screen_sizes[
                    lod_index
                ],
                influence_limits[
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
        0,
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
    # 1. Detect skeleton policy
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
    # new_lod_count = 0 (keep current number of LODs)
    # Only policies with explicit LOD0 removals rebuild the base (PXA)
    # --------------------------------------------------------

    log(
        "{}: regenerating generated LODs..."
        .format(
            asset_name
        )
    )

    regenerate_base_lod = POLICY_SETTINGS[policy_name]["regenerate_base_lod"]
    if regenerate_base_lod:
        log("{}: rebuilding LOD0 at 100% geometry retention for {} bone removals.".format(
            asset_name, len(BONE_POLICIES[policy_name][0])))

    regeneration_success = (
        unreal.SkeletalMeshEditorSubsystem
        .regenerate_lod(
            mesh,
            0,
            REGENERATE_IMPORTED_LODS,
            regenerate_base_lod
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
# This is the function called by the Editor Utility Blueprint.
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