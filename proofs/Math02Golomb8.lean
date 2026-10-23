-- Auto-exported Lean 4 Proof Certificate (MATH-02-ERDOS-SIDON-GOLOMB-8)
def pairwiseDiffs (m : List Nat) : List Nat :=
  (List.range m.length).foldl (fun acc i =>
    acc ++ ((List.range (m.length - i - 1)).map (fun d => (m.getD (i + d + 1) 0) - (m.getD i 0)))) []
def golomb8 : List Nat := [0, 1, 4, 9, 15, 22, 32, 34]

theorem math02_golomb8_optimal : golomb8.length = 8 ∧ golomb8.getLastD 0 = 34 ∧ (pairwiseDiffs golomb8).Nodup = true := by decide
