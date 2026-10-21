---------------------------- MODULE AEIBStation1And2 ----------------------------
EXTENDS Naturals, Sequences, TLC
CONSTANTS MaxBudget, Amount
VARIABLES budget,          \* Available budget pool
          escrow,          \* Amount reserved (Try phase)
          confirmed,       \* Amount settled (Confirm phase)
          state,           \* State machine: "IDLE", "DISPATCHED", "INDETERMINATE", "SETTLED"
          retries
vars == <<budget, escrow, confirmed, state, retries>>

Init ==
    /\ budget = MaxBudget
    /\ escrow = 0
    /\ confirmed = 0
    /\ state = "IDLE"
    /\ retries = 0

\* Station 1: Atomic Try reservation
TryReserve ==
    /\ state = "IDLE"
    /\ budget >= Amount
    /\ budget' = budget - Amount
    /\ escrow' = escrow + Amount
    /\ confirmed' = confirmed
    /\ state' = "DISPATCHED"
    /\ retries' = 0

\* Network drops / 504 timeout -> Latch
LatchIndeterminate ==
    /\ state = "DISPATCHED"
    /\ state' = "INDETERMINATE"
    /\ UNCHANGED <<budget, escrow, confirmed, retries>>

\* Resolution: Confirm (Target confirms it executed)
Confirm ==
    /\ state \in {"DISPATCHED", "INDETERMINATE"}
    /\ state' = "SETTLED"
    /\ escrow' = escrow - Amount
    /\ confirmed' = confirmed + Amount
    /\ UNCHANGED <<budget, retries>>

\* Resolution: Refute (Target confirms it failed, release escrow)
Refute ==
    /\ state \in {"DISPATCHED", "INDETERMINATE"}
    /\ state' = "IDLE"
    /\ escrow' = escrow - Amount
    /\ budget' = budget + Amount
    /\ UNCHANGED <<confirmed, retries>>

\* Safety Invariant: No Double-Spend
\* You can NEVER have confirmed + escrow > MaxBudget
NoDoubleSpend == confirmed + escrow <= MaxBudget

\* Safety Invariant: No Blind Retries under Uncertainty
\* If state is "INDETERMINATE", retries can only increase via a specific Reconcile action
NoBlindRetries == (state = "INDETERMINATE") => (retries = 0)

\* Next state relation
Next ==
    \/ TryReserve
    \/ LatchIndeterminate
    \/ Confirm
    \/ Refute

Spec == Init /\ [][Next]_vars
=============================================================================
