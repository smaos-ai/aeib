-- Auto-exported Lean 4 Proof Certificate (FIN-SEC-15C3-5-PRETRADE)
def currentExposure : Int := 150000
def creditCap : Int := 250000
def maxSingleOrder : Int := 50000
def sec15c3_5_admissible (ord exp cap maxOrd : Int) : Bool :=
  (ord > 0) && (ord <= maxOrd) && ((exp + ord) <= cap)
def orderNotional : Int := 40000

theorem sec_15c3_5_pretrade_compliance : sec15c3_5_admissible orderNotional currentExposure creditCap maxSingleOrder = true := by decide
