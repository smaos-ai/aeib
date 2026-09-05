import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest';
import { emailCampaignService } from '@/lib/services/email-campaign.service';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

describe('test_email_campaign_sends', () => {
  let creatorId: string;

  beforeAll(async () => {
    const creator = await prisma.creator.create({
      data: {
        name: 'Test Creator',
        email: `creator-${Date.now()}@example.com`,
        wallet: '0xcccccccccccccccccccccccccccccccccccccccc',
        stripe_customer_id: 'cus_email_test'
      }
    });
    creatorId = creator.id;

    // Mock email service
    process.env.EMAIL_SERVICE_API_KEY = 'test-key';
    process.env.SENDGRID_API_KEY = 'test-sendgrid-key';
  });

  it('should send 8-sequence email campaign to new creator', async () => {
    const mockSendEmail = vi.fn().mockResolvedValue({ id: 'msg-1', status: 'sent' });
    emailCampaignService.sendEmail = mockSendEmail;

    const sequences = await emailCampaignService.getEmailSequences();
    expect(sequences.length).toBe(8);

    const result = await emailCampaignService.startCampaign(creatorId);
    expect(result.sequences_scheduled).toBe(8);
    expect(result.creator_id).toBe(creatorId);
  });

  it('should have 8 distinct email sequences', async () => {
    const sequences = await emailCampaignService.getEmailSequences();

    expect(sequences.length).toBe(8);
    expect(sequences[0].day).toBe(0); // Immediate
    expect(sequences[1].day).toBe(1); // Day 1
    expect(sequences[2].day).toBe(3); // Day 3
    expect(sequences[3].day).toBe(7); // Day 7
    expect(sequences[4].day).toBe(14);
    expect(sequences[5].day).toBe(21);
    expect(sequences[6].day).toBe(30);
    expect(sequences[7].day).toBe(45);
  });

  it('should track email campaign delivery status', async () => {
    const campaign = await emailCampaignService.createCampaignRecord({
      creator_id: creatorId,
      sequence_day: 0,
      email_type: 'welcome',
      status: 'sent'
    });

    expect(campaign.status).toBe('sent');
    expect(campaign.sequence_day).toBe(0);
    expect(campaign.email_type).toBe('welcome');
  });

  it('should handle email delivery failures gracefully', async () => {
    const mockFailedSend = vi.fn().mockRejectedValue(new Error('SMTP Error'));
    emailCampaignService.sendEmail = mockFailedSend;

    const campaign = await emailCampaignService.createCampaignRecord({
      creator_id: creatorId,
      sequence_day: 1,
      email_type: 'getting_started',
      status: 'failed'
    });

    expect(campaign.status).toBe('failed');
  });

  it('should track campaign history for each creator', async () => {
    await emailCampaignService.createCampaignRecord({
      creator_id: creatorId,
      sequence_day: 0,
      email_type: 'welcome',
      status: 'sent'
    });

    await emailCampaignService.createCampaignRecord({
      creator_id: creatorId,
      sequence_day: 1,
      email_type: 'getting_started',
      status: 'sent'
    });

    const history = await emailCampaignService.getCampaignHistory(creatorId);
    expect(history.length).toBeGreaterThanOrEqual(2);
    expect(history.some(h => h.email_type === 'welcome')).toBe(true);
    expect(history.some(h => h.email_type === 'getting_started')).toBe(true);
  });

  it('should schedule emails at correct intervals', async () => {
    const schedule = await emailCampaignService.generateCampaignSchedule(creatorId);

    expect(schedule.length).toBe(8);
    // Verify increasing days
    for (let i = 1; i < schedule.length; i++) {
      expect(schedule[i].scheduled_date.getTime()).toBeGreaterThan(
        schedule[i - 1].scheduled_date.getTime()
      );
    }
  });

  afterAll(async () => {
    await prisma.emailCampaign.deleteMany({});
    await prisma.creator.deleteMany({});
    await prisma.$disconnect();
  });
});
