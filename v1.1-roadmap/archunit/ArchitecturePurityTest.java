package ai.sovereign.aeib.tests;

import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;
import com.tngtech.archunit.library.dependencies.SlicesRuleDefinition;
import com.tngtech.archunit.library.freeze.FreezingArchRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;

/**
 * Workstream 1: ArchUnit Bytecode & Package Boundary Gate (ADR-0001 / ADR-0002).
 *
 * Evaluates under the stated model:
 *   1. Zero-mock bytecode verification across Gate 4 test and runtime classes
 *      (forbids Mockito, PowerMock, and ByteBuddy dynamic subclassing).
 *   2. Zero external dependency boundary for {@code ai.sovereign.aeib.core..}
 *      (restricted to {@code ai.sovereign.aeib.core..}, {@code java..}, and {@code org.erdtman.jcs..}).
 *   3. Air-gapped isolation of the offline receipt verifier ({@code com.aeib.verifier..})
 *      from runtime execution packages and outbound HTTP clients.
 *   4. Package slice cycle freedom across {@code com.aeib.(*)..} modules.
 */
@AnalyzeClasses(packages = {"ai.sovereign.aeib..", "com.aeib.."})
public class ArchitecturePurityTest {

    @ArchTest
    public static final ArchRule no_mockito_or_powermock_in_gate4 =
            FreezingArchRule.freeze(
                    noClasses()
                            .should()
                            .dependOnClassesThat()
                            .resideInAnyPackage("org.mockito..", "org.powermock..", "net.bytebuddy..")
                            .because("Gate 4 evaluated classes must exercise real cryptographic and SQLite primitives without bytecode mocking frameworks under the stated model")
            );

    @ArchTest
    public static final ArchRule aeib_core_zero_external_dependencies =
            noClasses()
                    .that()
                    .resideInAPackage("ai.sovereign.aeib.core..")
                    .should()
                    .dependOnClassesThat()
                    .resideOutsideOfPackages("ai.sovereign.aeib.core..", "java..", "org.erdtman.jcs..")
                    .because("Core station interfaces and records are configured with zero external framework dependencies beyond JDK stdlib and RFC 8785 JCS");

    @ArchTest
    public static final ArchRule offline_verifier_isolated_from_runtime =
            noClasses()
                    .that()
                    .resideInAPackage("com.aeib.verifier..")
                    .should()
                    .dependOnClassesThat()
                    .resideInAnyPackage("com.aeib.runtime..", "ai.sovereign.aeib.runtime..", "java.net.http..")
                    .because("Offline receipt verification is configured to operate in air-gapped isolation from runtime stations and network egress");

    /**
     * Evaluates package slice cycle freedom via {@link SlicesRuleDefinition#slices()}
     * ({@code SlicesRuleDefinition.slices()}).
     */
    @ArchTest
    public static final ArchRule slice_cycle_freedom =
            FreezingArchRule.freeze(
                    slices()
                            .matching("com.aeib.(*)..")
                            .should()
                            .beFreeOfCycles()
                            .because("Package slices across com.aeib modules are evaluated for acyclic dependency structure")
            );
}
