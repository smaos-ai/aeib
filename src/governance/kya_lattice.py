"""
KYA "Only-Tighten" Inbound Gate Rule
Enforces that delegated tool authority can only contract, never expand.
"""


def verify_only_tighten_lattice(
    parent_permissions: set, delegated_permissions: set
) -> bool:
    """
    KYA Rule: Delegated permissions must be a strict subset of parent permissions.
    Enforces the lattice invariant that delegation can only restrict, not expand.

    Args:
        parent_permissions: Set of permissions held by the parent/delegator
        delegated_permissions: Set of permissions being delegated

    Returns:
        True if delegation respects the lattice

    Raises:
        PermissionError: If delegated permissions exceed parent permissions
    """
    if not delegated_permissions.issubset(parent_permissions):
        disallowed = delegated_permissions - parent_permissions
        raise PermissionError(
            f"[KYA LATTICE VIOLATION] Delegated agent attempted privilege escalation. "
            f"Unauthorized scopes requested: {disallowed}. "
            f"Parent permissions: {parent_permissions}. "
            f"Delegated permissions: {delegated_permissions}"
        )
    return True


# Test cases
if __name__ == "__main__":
    # Valid: Strict subset
    parent = {"READ", "WRITE", "DELETE"}
    delegated = {"READ", "WRITE"}
    assert verify_only_tighten_lattice(parent, delegated) == True
    print("✓ Valid delegation: subset")

    # Invalid: Expansion attempt
    try:
        parent = {"READ", "WRITE"}
        delegated = {"READ", "WRITE", "ADMIN"}
        verify_only_tighten_lattice(parent, delegated)
        print("✗ FAILED: Should have raised PermissionError")
    except PermissionError as e:
        print(f"✓ Caught escalation attempt: {e}")

    # Valid: Empty delegation (no permissions)
    parent = {"READ", "WRITE"}
    delegated = set()
    assert verify_only_tighten_lattice(parent, delegated) == True
    print("✓ Valid delegation: empty set")
