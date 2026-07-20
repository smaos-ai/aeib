import { describe, it, expect } from 'vitest';
import { emailCampaignService } from '@/lib/services/email-campaign.service';

describe('test_email_campaign_sends', () => {
  it('should have 8-sequence email campaign', () => {
    const sequences = emailCampaignService.getEmailSequences();
    expect(sequences.length).toBe(8);
  });

  it('should have correct day schedule for sequences', () => {
    const sequences = emailCampaignService.getEmailSequences();

    expect(sequences[0].day).toBe(0);   // Immediate
    expect(sequences[1].day).toBe(1);   // Day 1
    expect(sequences[2].day).toBe(3);   // Day 3
    expect(sequences[3].day).toBe(7);   // Day 7
    expect(sequences[4].day).toBe(14);  // Day 14
    expect(sequences[5].day).toBe(21);  // Day 21
    expect(sequences[6].day).toBe(30);  // Day 30
    expect(sequences[7].day).toBe(45);  // Day 45
  });

  it('should have distinct email types for each sequence', () => {
    const sequences = emailCampaignService.getEmailSequences();
    const types = sequences.map(s => s.type);
    const uniqueTypes = new Set(types);

    expect(uniqueTypes.size).toBe(8); // All unique
  });

  it('should have proper email type naming', () => {
    const sequences = emailCampaignService.getEmailSequences();
    const expectedTypes = [
      'welcome',
      'getting_started',
      'feature_highlight',
      'success_story',
      'monetization_tips',
      'community_feature',
      'upgrade_offer',
      'retention'
    ];

    sequences.forEach((seq, idx) => {
      expect(seq.type).toBe(expectedTypes[idx]);
    });
  });

  it('should have subject lines for each sequence', () => {
    const sequences = emailCampaignService.getEmailSequences();

    sequences.forEach(seq => {
      expect(seq.subject).toBeTruthy();
      expect(seq.subject.length).toBeGreaterThan(0);
    });
  });

  it('should have template references for each sequence', () => {
    const sequences = emailCampaignService.getEmailSequences();

    sequences.forEach(seq => {
      expect(seq.template).toBeTruthy();
      expect(seq.template.length).toBeGreaterThan(0);
    });
  });

  it('should have increasing days in campaign schedule', () => {
    const sequences = emailCampaignService.getEmailSequences();

    for (let i = 1; i < sequences.length; i++) {
      expect(sequences[i].day).toBeGreaterThan(sequences[i - 1].day);
    }
  });

  it('should provide welcome email as first sequence', () => {
    const sequences = emailCampaignService.getEmailSequences();

    expect(sequences[0].type).toBe('welcome');
    expect(sequences[0].day).toBe(0);
  });

  it('should provide retention email as final sequence', () => {
    const sequences = emailCampaignService.getEmailSequences();

    expect(sequences[sequences.length - 1].type).toBe('retention');
    expect(sequences[sequences.length - 1].day).toBe(45);
  });

  it('should have appropriate spacing between sequences', () => {
    const sequences = emailCampaignService.getEmailSequences();

    // Day 0 -> 1: 1 day gap
    expect(sequences[1].day - sequences[0].day).toBe(1);

    // Day 1 -> 3: 2 day gap
    expect(sequences[2].day - sequences[1].day).toBe(2);

    // Day 3 -> 7: 4 day gap
    expect(sequences[3].day - sequences[2].day).toBe(4);

    // Day 7 -> 14: 7 day gap
    expect(sequences[4].day - sequences[3].day).toBe(7);

    // Day 14 -> 21: 7 day gap
    expect(sequences[5].day - sequences[4].day).toBe(7);

    // Day 21 -> 30: 9 day gap
    expect(sequences[6].day - sequences[5].day).toBe(9);

    // Day 30 -> 45: 15 day gap
    expect(sequences[7].day - sequences[6].day).toBe(15);
  });
});
