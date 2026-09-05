import { describe, it, expect, beforeEach } from 'vitest';
import { SAMLManager } from '../src/lib/saml';

describe('SAML 2.0 Manager', () => {
  let samlManager: SAMLManager;

  beforeEach(() => {
    samlManager = new SAMLManager({
      entryPoint: 'https://idp.example.com/sso',
      issuer: 'urn:example:sp',
      cert: Buffer.from(''),
      identifierFormat: 'urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress'
    });
  });

  describe('AuthN Request Generation', () => {
    it('should generate valid SAML AuthnRequest', () => {
      const authnRequest = samlManager.generateAuthnRequest();
      expect(authnRequest).toBeDefined();
      expect(authnRequest.id).toBeDefined();
      expect(authnRequest.issueInstant).toBeDefined();
      expect(authnRequest.assertionConsumerServiceURL).toBeDefined();
    });

    it('should include unique request ID', () => {
      const req1 = samlManager.generateAuthnRequest();
      const req2 = samlManager.generateAuthnRequest();
      expect(req1.id).not.toBe(req2.id);
    });

    it('should include valid issue instant', () => {
      const authnRequest = samlManager.generateAuthnRequest();
      const issueTime = new Date(authnRequest.issueInstant).getTime();
      const now = Date.now();
      expect(Math.abs(now - issueTime)).toBeLessThan(5000); // Within 5 seconds
    });

    it('should encode AuthnRequest to Base64', () => {
      const encoded = samlManager.encodeAuthnRequest();
      expect(encoded).toBeDefined();
      expect(typeof encoded).toBe('string');
      expect(encoded.length).toBeGreaterThan(0);
    });

    it('should generate valid redirect URL', () => {
      const url = samlManager.getRedirectURL();
      expect(url).toContain('https://idp.example.com/sso');
      expect(url).toContain('SAMLRequest=');
      expect(url).toContain('RelayState=');
    });
  });

  describe('Response Parsing & Validation', () => {
    it('should parse valid SAML response', () => {
      const samlResponse = samlManager.generateMockSAMLResponse({
        nameID: 'user@example.com',
        email: 'user@example.com',
        givenName: 'John',
        surname: 'Doe'
      });

      const parsed = samlManager.parseSAMLResponse(samlResponse);
      expect(parsed).toBeDefined();
      expect(parsed.nameID).toBe('user@example.com');
      expect(parsed.attributes).toBeDefined();
    });

    it('should extract email from SAML attributes', () => {
      const samlResponse = samlManager.generateMockSAMLResponse({
        nameID: 'user123@example.com',
        email: 'user123@example.com',
        givenName: 'Jane',
        surname: 'Smith'
      });

      const parsed = samlManager.parseSAMLResponse(samlResponse);
      expect(parsed.email).toBe('user123@example.com');
    });

    it('should extract all required attributes', () => {
      const samlResponse = samlManager.generateMockSAMLResponse({
        nameID: 'employee@corp.com',
        email: 'employee@corp.com',
        givenName: 'Robert',
        surname: 'Johnson',
        departmentCode: 'ENG-001',
        role: 'Senior Engineer'
      });

      const parsed = samlManager.parseSAMLResponse(samlResponse);
      expect(parsed.attributes?.givenName).toBe('Robert');
      expect(parsed.attributes?.surname).toBe('Johnson');
      expect(parsed.attributes?.departmentCode).toBe('ENG-001');
      expect(parsed.attributes?.role).toBe('Senior Engineer');
    });

    it('should validate assertion signature', () => {
      const samlResponse = samlManager.generateMockSAMLResponse({
        nameID: 'user@example.com',
        email: 'user@example.com'
      });

      const isValid = samlManager.validateSignature(samlResponse);
      expect(isValid).toBe(true);
    });

    it('should reject tampered response', () => {
      const samlResponse = samlManager.generateMockSAMLResponse({
        nameID: 'user@example.com',
        email: 'user@example.com'
      });

      const tampered = samlResponse.replace(/user@example\.com/g, 'admin@example.com');
      const isValid = samlManager.validateSignature(tampered);
      expect(isValid).toBe(false);
    });
  });

  describe('Session Management', () => {
    it('should track SAML session', () => {
      const sessionID = samlManager.generateSessionID();
      expect(sessionID).toBeDefined();
      expect(sessionID.length).toBeGreaterThan(0);
    });

    it('should validate session ID format', () => {
      const sessionID = samlManager.generateSessionID();
      const isValid = samlManager.validateSessionID(sessionID);
      expect(isValid).toBe(true);
    });

    it('should store AuthnRequest context', () => {
      const authnRequest = samlManager.generateAuthnRequest();
      samlManager.storeRequestContext(authnRequest.id, { relayState: 'state123' });

      const context = samlManager.getRequestContext(authnRequest.id);
      expect(context).toBeDefined();
      expect(context?.relayState).toBe('state123');
    });

    it('should validate response matches request', () => {
      const authnRequest = samlManager.generateAuthnRequest();
      samlManager.storeRequestContext(authnRequest.id, {});

      const samlResponse = samlManager.generateMockSAMLResponse({
        nameID: 'user@example.com',
        email: 'user@example.com',
        inResponseTo: authnRequest.id
      });

      const matches = samlManager.validateResponseToRequest(samlResponse, authnRequest.id);
      expect(matches).toBe(true);
    });

    it('should reject response for unknown request', () => {
      const samlResponse = samlManager.generateMockSAMLResponse({
        nameID: 'user@example.com',
        email: 'user@example.com',
        inResponseTo: 'unknown-request-id'
      });

      const matches = samlManager.validateResponseToRequest(samlResponse, 'unknown-request-id');
      expect(matches).toBe(false);
    });
  });

  describe('Attribute Mapping', () => {
    it('should map SAML attributes to user profile', () => {
      const samlResponse = samlManager.generateMockSAMLResponse({
        nameID: 'contractor@external.com',
        email: 'contractor@external.com',
        givenName: 'Alice',
        surname: 'Williams',
        organization: 'ExtCorp'
      });

      const parsed = samlManager.parseSAMLResponse(samlResponse);
      const userProfile = samlManager.mapToUserProfile(parsed);

      expect(userProfile.username).toBe('contractor@external.com');
      expect(userProfile.email).toBe('contractor@external.com');
      expect(userProfile.firstName).toBe('Alice');
      expect(userProfile.lastName).toBe('Williams');
    });

    it('should handle missing optional attributes', () => {
      const samlResponse = samlManager.generateMockSAMLResponse({
        nameID: 'minimal@example.com',
        email: 'minimal@example.com'
      });

      const parsed = samlManager.parseSAMLResponse(samlResponse);
      const userProfile = samlManager.mapToUserProfile(parsed);

      expect(userProfile.email).toBe('minimal@example.com');
      expect(userProfile.firstName).toBeUndefined();
      expect(userProfile.lastName).toBeUndefined();
    });

    it('should preserve custom attributes in profile', () => {
      const samlResponse = samlManager.generateMockSAMLResponse({
        nameID: 'custom@example.com',
        email: 'custom@example.com',
        department: 'Finance',
        costCenter: '2024-Q4'
      });

      const parsed = samlManager.parseSAMLResponse(samlResponse);
      const userProfile = samlManager.mapToUserProfile(parsed);

      expect(userProfile.customAttributes?.department).toBe('Finance');
      expect(userProfile.customAttributes?.costCenter).toBe('2024-Q4');
    });
  });

  describe('Metadata & Configuration', () => {
    it('should generate SP metadata', () => {
      const metadata = samlManager.generateMetadata();
      expect(metadata).toBeDefined();
      expect(metadata).toContain('EntityDescriptor');
      expect(metadata).toContain('urn:example:sp');
    });

    it('should include AssertionConsumerService in metadata', () => {
      const metadata = samlManager.generateMetadata();
      expect(metadata).toContain('AssertionConsumerService');
    });

    it('should include SingleLogoutService in metadata', () => {
      const metadata = samlManager.generateMetadata();
      expect(metadata).toContain('SingleLogoutService');
    });
  });
});
