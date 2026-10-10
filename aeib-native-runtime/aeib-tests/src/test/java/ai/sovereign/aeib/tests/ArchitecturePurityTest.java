package ai.sovereign.aeib.tests;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.lang.ArchRule;
import org.junit.jupiter.api.Test;

import java.net.ServerSocket;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

/**
 * ArchUnit Pre-Push Architectural Wall:
 * Enforces zero-mock wire realism in Gate 4, strict module boundary isolation,
 * and zero external dependencies in aeib-core.
 */
public class ArchitecturePurityTest {

    private static final JavaClasses ALL_CLASSES = new ClassFileImporter()
        .importPackages("ai.sovereign.aeib", "com.aeib");

    @Test
    public void noMockitoOrPowerMockAnywhereInBoundaryOrTests() {
        ArchRule rule = noClasses()
            .that().resideInAnyPackage("ai.sovereign.aeib..", "com.aeib..")
            .should().dependOnClassesThat().resideInAnyPackage(
                "org.mockito..",
                "org.powermock..",
                "org.easymock.."
            )
            .because("Gate 4 and AEIB runtime components must exercise real wire sockets and real SunEC cryptography without mock frameworks");

        rule.check(ALL_CLASSES);
    }

    @Test
    public void coreModuleMustRemainZeroExternalDependency() {
        ArchRule rule = classes()
            .that().resideInAPackage("ai.sovereign.aeib.core..")
            .should().onlyDependOnClassesThat().resideInAnyPackage(
                "java..",
                "ai.sovereign.aeib.core.."
            )
            .because("aeib-core is a portable zero-dependency contract module");

        rule.check(ALL_CLASSES);
    }

    @Test
    public void standaloneVerifierMustNotDependOnRuntimeEngine() {
        ArchRule rule = noClasses()
            .that().resideInAPackage("com.aeib.verifier..")
            .should().dependOnClassesThat().resideInAPackage("com.aeib.runtime..")
            .because("The standalone offline verifier must remain strictly isolated from the runtime execution engine");

        rule.check(ALL_CLASSES);
    }

    @Test
    public void gate4IntegrationTestMustBindRealServerSockets() {
        ArchRule rule = classes()
            .that().haveSimpleName("Gate4IntegrationTest")
            .should().dependOnClassesThat().areAssignableTo(ServerSocket.class)
            .because("Gate 4 integration tests must exercise real TCP socket listeners rather than simulated mocks");

        rule.check(ALL_CLASSES);
    }
}
