-- Auto-exported Lean 4 Proof Certificate (MATH-06-LABS-BARKER-13)
def autocorr (s : List Int) (k : Nat) : Int :=
  (List.range (s.length - k)).foldl (fun acc i => acc + (s.getD i 0) * (s.getD (i + k) 0)) 0
def sidelobeEnergy (s : List Int) : Int :=
  (List.range 12).foldl (fun acc idx => let c := autocorr s (idx + 1); acc + c * c) 0
def barker13 : List Int := [1, 1, 1, 1, 1, -1, -1, 1, 1, -1, 1, -1, 1]

theorem math06_labs_barker13_optimal : barker13.length = 13 ∧ sidelobeEnergy barker13 = 6 := by decide
