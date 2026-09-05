import Lake
open Lake DSL

package siss_formal_verification where
  name := "siss_formal_verification"
  version := (0, 1, 0)
  lakeDir := "./formal-verification/lean"

lean_lib SissFormVerif where
  srcDir := "./formal-verification/lean"
  roots := [
    "prelude.types",
    "siss_cipo",
    "siss_gde",
    "siss_spec_to_ship",
    "siss_monge_gap"
  ]

@[default_target]
lean_exe formal_verification where
  root := "formal-verification/lean/main"
  supportInterop := false
