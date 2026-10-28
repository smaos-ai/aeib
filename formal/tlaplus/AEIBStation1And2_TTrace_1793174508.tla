---- MODULE AEIBStation1And2_TTrace_1793174508 ----
EXTENDS Sequences, AEIBStation1And2_TEConstants, TLCExt, Toolbox, Naturals, TLC, AEIBStation1And2

_expression ==
    LET AEIBStation1And2_TEExpression == INSTANCE AEIBStation1And2_TEExpression
    IN AEIBStation1And2_TEExpression!expression
----

_trace ==
    LET AEIBStation1And2_TETrace == INSTANCE AEIBStation1And2_TETrace
    IN AEIBStation1And2_TETrace!trace
----

_inv ==
    ~(
        TLCGet("level") = Len(_TETrace)
        /\
        opAmount = ((op1 :> 1 @@ op2 :> 0))
        /\
        settledMinor = (1)
        /\
        opState = ((op1 :> "CONFIRMED" @@ op2 :> "IDLE"))
        /\
        inflight = ((op1 :> 0 @@ op2 :> 0))
        /\
        readbackResult = ((op1 :> "NONE" @@ op2 :> "NONE"))
        /\
        targetEffects = ((op1 :> 2 @@ op2 :> 0))
        /\
        regenerated = ((op1 :> FALSE @@ op2 :> FALSE))
        /\
        latchState = ((op1 :> "NONE" @@ op2 :> "NONE"))
        /\
        fenceBelow = ((op1 :> 0 @@ op2 :> 0))
        /\
        releaseEvidence = ((op1 :> "NOT_APPLIED" @@ op2 :> "NONE"))
        /\
        readbackEffects = ((op1 :> 0 @@ op2 :> 0))
        /\
        reservedMinor = (0)
        /\
        attempts = ((op1 :> 2 @@ op2 :> 0))
    )
----

_init ==
    /\ inflight = _TETrace[1].inflight
    /\ fenceBelow = _TETrace[1].fenceBelow
    /\ releaseEvidence = _TETrace[1].releaseEvidence
    /\ readbackResult = _TETrace[1].readbackResult
    /\ opState = _TETrace[1].opState
    /\ targetEffects = _TETrace[1].targetEffects
    /\ attempts = _TETrace[1].attempts
    /\ regenerated = _TETrace[1].regenerated
    /\ reservedMinor = _TETrace[1].reservedMinor
    /\ latchState = _TETrace[1].latchState
    /\ settledMinor = _TETrace[1].settledMinor
    /\ readbackEffects = _TETrace[1].readbackEffects
    /\ opAmount = _TETrace[1].opAmount
----

_next ==
    /\ \E i,j \in DOMAIN _TETrace:
        /\ \/ /\ j = i + 1
              /\ i = TLCGet("level")
        /\ inflight  = _TETrace[i].inflight
        /\ inflight' = _TETrace[j].inflight
        /\ fenceBelow  = _TETrace[i].fenceBelow
        /\ fenceBelow' = _TETrace[j].fenceBelow
        /\ releaseEvidence  = _TETrace[i].releaseEvidence
        /\ releaseEvidence' = _TETrace[j].releaseEvidence
        /\ readbackResult  = _TETrace[i].readbackResult
        /\ readbackResult' = _TETrace[j].readbackResult
        /\ opState  = _TETrace[i].opState
        /\ opState' = _TETrace[j].opState
        /\ targetEffects  = _TETrace[i].targetEffects
        /\ targetEffects' = _TETrace[j].targetEffects
        /\ attempts  = _TETrace[i].attempts
        /\ attempts' = _TETrace[j].attempts
        /\ regenerated  = _TETrace[i].regenerated
        /\ regenerated' = _TETrace[j].regenerated
        /\ reservedMinor  = _TETrace[i].reservedMinor
        /\ reservedMinor' = _TETrace[j].reservedMinor
        /\ latchState  = _TETrace[i].latchState
        /\ latchState' = _TETrace[j].latchState
        /\ settledMinor  = _TETrace[i].settledMinor
        /\ settledMinor' = _TETrace[j].settledMinor
        /\ readbackEffects  = _TETrace[i].readbackEffects
        /\ readbackEffects' = _TETrace[j].readbackEffects
        /\ opAmount  = _TETrace[i].opAmount
        /\ opAmount' = _TETrace[j].opAmount

\* Uncomment the ASSUME below to write the states of the error trace
\* to the given file in Json format. Note that you can pass any tuple
\* to `JsonSerialize`. For example, a sub-sequence of _TETrace.
    \* ASSUME
    \*     LET J == INSTANCE Json
    \*         IN J!JsonSerialize("AEIBStation1And2_TTrace_1793174508.json", _TETrace)

=============================================================================

 Note that you can extract this module `AEIBStation1And2_TEExpression`
  to a dedicated file to reuse `expression` (the module in the 
  dedicated `AEIBStation1And2_TEExpression.tla` file takes precedence 
  over the module `AEIBStation1And2_TEExpression` below).

---- MODULE AEIBStation1And2_TEExpression ----
EXTENDS Sequences, AEIBStation1And2_TEConstants, TLCExt, Toolbox, Naturals, TLC, AEIBStation1And2

expression == 
    [
        \* To hide variables of the `AEIBStation1And2` spec from the error trace,
        \* remove the variables below.  The trace will be written in the order
        \* of the fields of this record.
        inflight |-> inflight
        ,fenceBelow |-> fenceBelow
        ,releaseEvidence |-> releaseEvidence
        ,readbackResult |-> readbackResult
        ,opState |-> opState
        ,targetEffects |-> targetEffects
        ,attempts |-> attempts
        ,regenerated |-> regenerated
        ,reservedMinor |-> reservedMinor
        ,latchState |-> latchState
        ,settledMinor |-> settledMinor
        ,readbackEffects |-> readbackEffects
        ,opAmount |-> opAmount
        
        \* Put additional constant-, state-, and action-level expressions here:
        \* ,_stateNumber |-> _TEPosition
        \* ,_inflightUnchanged |-> inflight = inflight'
        
        \* Format the `inflight` variable as Json value.
        \* ,_inflightJson |->
        \*     LET J == INSTANCE Json
        \*     IN J!ToJson(inflight)
        
        \* Lastly, you may build expressions over arbitrary sets of states by
        \* leveraging the _TETrace operator.  For example, this is how to
        \* count the number of times a spec variable changed up to the current
        \* state in the trace.
        \* ,_inflightModCount |->
        \*     LET F[s \in DOMAIN _TETrace] ==
        \*         IF s = 1 THEN 0
        \*         ELSE IF _TETrace[s].inflight # _TETrace[s-1].inflight
        \*             THEN 1 + F[s-1] ELSE F[s-1]
        \*     IN F[_TEPosition - 1]
    ]

=============================================================================



Parsing and semantic processing can take forever if the trace below is long.
 In this case, it is advised to uncomment the module below to deserialize the
 trace from a generated binary file.

\*
\*---- MODULE AEIBStation1And2_TETrace ----
\*EXTENDS IOUtils, AEIBStation1And2_TEConstants, TLC, AEIBStation1And2
\*
\*trace == IODeserialize("AEIBStation1And2_TTrace_1793174508.bin", TRUE)
\*
\*=============================================================================
\*

---- MODULE AEIBStation1And2_TETrace ----
EXTENDS AEIBStation1And2_TEConstants, TLC, AEIBStation1And2

trace == 
    <<
    ([opAmount |-> (op1 :> 0 @@ op2 :> 0),settledMinor |-> 0,opState |-> (op1 :> "IDLE" @@ op2 :> "IDLE"),inflight |-> (op1 :> 0 @@ op2 :> 0),readbackResult |-> (op1 :> "NONE" @@ op2 :> "NONE"),targetEffects |-> (op1 :> 0 @@ op2 :> 0),regenerated |-> (op1 :> FALSE @@ op2 :> FALSE),latchState |-> (op1 :> "NONE" @@ op2 :> "NONE"),fenceBelow |-> (op1 :> 0 @@ op2 :> 0),releaseEvidence |-> (op1 :> "NONE" @@ op2 :> "NONE"),readbackEffects |-> (op1 :> 0 @@ op2 :> 0),reservedMinor |-> 0,attempts |-> (op1 :> 0 @@ op2 :> 0)]),
    ([opAmount |-> (op1 :> 1 @@ op2 :> 0),settledMinor |-> 0,opState |-> (op1 :> "DISPATCHED" @@ op2 :> "IDLE"),inflight |-> (op1 :> 0 @@ op2 :> 0),readbackResult |-> (op1 :> "NONE" @@ op2 :> "NONE"),targetEffects |-> (op1 :> 0 @@ op2 :> 0),regenerated |-> (op1 :> FALSE @@ op2 :> FALSE),latchState |-> (op1 :> "NONE" @@ op2 :> "NONE"),fenceBelow |-> (op1 :> 0 @@ op2 :> 0),releaseEvidence |-> (op1 :> "NONE" @@ op2 :> "NONE"),readbackEffects |-> (op1 :> 0 @@ op2 :> 0),reservedMinor |-> 1,attempts |-> (op1 :> 1 @@ op2 :> 0)]),
    ([opAmount |-> (op1 :> 1 @@ op2 :> 0),settledMinor |-> 0,opState |-> (op1 :> "INDETERMINATE" @@ op2 :> "IDLE"),inflight |-> (op1 :> 1 @@ op2 :> 0),readbackResult |-> (op1 :> "NONE" @@ op2 :> "NONE"),targetEffects |-> (op1 :> 0 @@ op2 :> 0),regenerated |-> (op1 :> FALSE @@ op2 :> FALSE),latchState |-> (op1 :> "LATCHED" @@ op2 :> "NONE"),fenceBelow |-> (op1 :> 0 @@ op2 :> 0),releaseEvidence |-> (op1 :> "NONE" @@ op2 :> "NONE"),readbackEffects |-> (op1 :> 0 @@ op2 :> 0),reservedMinor |-> 1,attempts |-> (op1 :> 1 @@ op2 :> 0)]),
    ([opAmount |-> (op1 :> 1 @@ op2 :> 0),settledMinor |-> 0,opState |-> (op1 :> "INDETERMINATE" @@ op2 :> "IDLE"),inflight |-> (op1 :> 1 @@ op2 :> 0),readbackResult |-> (op1 :> "NOT_APPLIED" @@ op2 :> "NONE"),targetEffects |-> (op1 :> 0 @@ op2 :> 0),regenerated |-> (op1 :> FALSE @@ op2 :> FALSE),latchState |-> (op1 :> "LATCHED" @@ op2 :> "NONE"),fenceBelow |-> (op1 :> 0 @@ op2 :> 0),releaseEvidence |-> (op1 :> "NONE" @@ op2 :> "NONE"),readbackEffects |-> (op1 :> 1 @@ op2 :> 0),reservedMinor |-> 1,attempts |-> (op1 :> 1 @@ op2 :> 0)]),
    ([opAmount |-> (op1 :> 1 @@ op2 :> 0),settledMinor |-> 0,opState |-> (op1 :> "INDETERMINATE" @@ op2 :> "IDLE"),inflight |-> (op1 :> 0 @@ op2 :> 0),readbackResult |-> (op1 :> "NOT_APPLIED" @@ op2 :> "NONE"),targetEffects |-> (op1 :> 1 @@ op2 :> 0),regenerated |-> (op1 :> FALSE @@ op2 :> FALSE),latchState |-> (op1 :> "LATCHED" @@ op2 :> "NONE"),fenceBelow |-> (op1 :> 0 @@ op2 :> 0),releaseEvidence |-> (op1 :> "NONE" @@ op2 :> "NONE"),readbackEffects |-> (op1 :> 1 @@ op2 :> 0),reservedMinor |-> 1,attempts |-> (op1 :> 1 @@ op2 :> 0)]),
    ([opAmount |-> (op1 :> 1 @@ op2 :> 0),settledMinor |-> 0,opState |-> (op1 :> "REFUTED" @@ op2 :> "IDLE"),inflight |-> (op1 :> 0 @@ op2 :> 0),readbackResult |-> (op1 :> "NOT_APPLIED" @@ op2 :> "NONE"),targetEffects |-> (op1 :> 1 @@ op2 :> 0),regenerated |-> (op1 :> FALSE @@ op2 :> FALSE),latchState |-> (op1 :> "RELEASED" @@ op2 :> "NONE"),fenceBelow |-> (op1 :> 0 @@ op2 :> 0),releaseEvidence |-> (op1 :> "NOT_APPLIED" @@ op2 :> "NONE"),readbackEffects |-> (op1 :> 1 @@ op2 :> 0),reservedMinor |-> 0,attempts |-> (op1 :> 1 @@ op2 :> 0)]),
    ([opAmount |-> (op1 :> 1 @@ op2 :> 0),settledMinor |-> 0,opState |-> (op1 :> "DISPATCHED" @@ op2 :> "IDLE"),inflight |-> (op1 :> 0 @@ op2 :> 0),readbackResult |-> (op1 :> "NONE" @@ op2 :> "NONE"),targetEffects |-> (op1 :> 1 @@ op2 :> 0),regenerated |-> (op1 :> FALSE @@ op2 :> FALSE),latchState |-> (op1 :> "NONE" @@ op2 :> "NONE"),fenceBelow |-> (op1 :> 0 @@ op2 :> 0),releaseEvidence |-> (op1 :> "NOT_APPLIED" @@ op2 :> "NONE"),readbackEffects |-> (op1 :> 0 @@ op2 :> 0),reservedMinor |-> 1,attempts |-> (op1 :> 2 @@ op2 :> 0)]),
    ([opAmount |-> (op1 :> 1 @@ op2 :> 0),settledMinor |-> 1,opState |-> (op1 :> "CONFIRMED" @@ op2 :> "IDLE"),inflight |-> (op1 :> 0 @@ op2 :> 0),readbackResult |-> (op1 :> "NONE" @@ op2 :> "NONE"),targetEffects |-> (op1 :> 2 @@ op2 :> 0),regenerated |-> (op1 :> FALSE @@ op2 :> FALSE),latchState |-> (op1 :> "NONE" @@ op2 :> "NONE"),fenceBelow |-> (op1 :> 0 @@ op2 :> 0),releaseEvidence |-> (op1 :> "NOT_APPLIED" @@ op2 :> "NONE"),readbackEffects |-> (op1 :> 0 @@ op2 :> 0),reservedMinor |-> 0,attempts |-> (op1 :> 2 @@ op2 :> 0)])
    >>
----


=============================================================================

---- MODULE AEIBStation1And2_TEConstants ----
EXTENDS AEIBStation1And2

CONSTANTS op1, op2

=============================================================================

---- CONFIG AEIBStation1And2_TTrace_1793174508 ----
CONSTANTS
    Operations = { op1 , op2 }
    SprintLimitMinor = 3
    MaxPerCallMinor = 2
    FencingEnabled = FALSE
    op2 = op2
    op1 = op1

INVARIANT
    _inv

CHECK_DEADLOCK
    \* CHECK_DEADLOCK off because of PROPERTY or INVARIANT above.
    FALSE

INIT
    _init

NEXT
    _next

CONSTANT
    _TETrace <- _trace

ALIAS
    _expression
=============================================================================
\* Generated on Wed Oct 28 08:01:48 UTC 2026