-- Auto-exported Lean 4 Proof Certificate (MATH-09-TAO-EQUATIONAL-MAGMA-1485)
-- Terence Tao Equational Theories Project: Central Groupoid Law (Eq 1485)
-- (x ◇ y) ◇ (y ◇ z) = y on Fin 4 refutes both Commutativity (Eq 43) and Associativity (Eq 4512)
def magmaOp (x y : Nat) : Nat :=
  2 * (x % 2) + ((y / 2) % 2)
def dom4 : List Nat := [0, 1, 2, 3]
def holdsEq1485 : Bool :=
  dom4.all (fun x => dom4.all (fun y => dom4.all (fun z =>
    magmaOp (magmaOp x y) (magmaOp y z) == y)))
def refutesCommutativity : Bool :=
  magmaOp 0 1 != magmaOp 1 0
def refutesAssociativity : Bool :=
  magmaOp (magmaOp 0 0) 2 != magmaOp 0 (magmaOp 0 2)

theorem math09_tao_central_groupoid_anti_implication :
    holdsEq1485 = true ∧ refutesCommutativity = true ∧ refutesAssociativity = true := by decide
