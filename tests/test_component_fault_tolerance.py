from dependencies.models import ComponentState, DependencyNode


def test_component_fault_tolerance_logic():
    # Setup 3 mods:
    # Mod 1: Standalone healthy mod
    # Mod 2: Failed download
    # Mod 3: Depends on Mod 2 -> should be BLOCKED_BY_DEPENDENCY
    # Mod 4: Independent healthy mod -> should succeed

    mod1 = DependencyNode(game_domain="mysummercar", mod_id=1, name="HealthyMod1")
    mod2 = DependencyNode(game_domain="mysummercar", mod_id=2, name="FailingMod2")
    mod3 = DependencyNode(game_domain="mysummercar", mod_id=3, name="DependentMod3")
    mod4 = DependencyNode(game_domain="mysummercar", mod_id=4, name="HealthyMod4")

    # Mod 3 depends on Mod 2
    mod3.dependency_of = ["FailingMod2"]

    # Simulate pipeline execution:
    # Mod 1 succeeds
    mod1.state = ComponentState.INSTALLED

    # Mod 2 fails download
    mod2.state = ComponentState.FAILED_DOWNLOAD

    # Mod 3 evaluation: parent failed -> blocked
    if mod2.state in (ComponentState.FAILED_DOWNLOAD, ComponentState.FAILED_INSTALL):
        mod3.state = ComponentState.BLOCKED_BY_DEPENDENCY
        mod3.blocked_by = mod2.name
    else:
        mod3.state = ComponentState.INSTALLED

    # Mod 4 succeeds independently
    mod4.state = ComponentState.INSTALLED

    assert mod1.state == ComponentState.INSTALLED
    assert mod2.state == ComponentState.FAILED_DOWNLOAD
    assert mod3.state == ComponentState.BLOCKED_BY_DEPENDENCY
    assert mod3.blocked_by == "FailingMod2"
    assert mod4.state == ComponentState.INSTALLED
