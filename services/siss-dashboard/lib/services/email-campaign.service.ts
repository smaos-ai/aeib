import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

export interface EmailSequence {
  day: number;
  type: string;
  subject: string;
  template: string;
}

export interface CampaignScheduleItem {
  sequence_day: number;
  email_type: string;
  scheduled_date: Date;
}

export interface CreateCampaignRecordInput {
  creator_id: string;
  sequence_day: number;
  email_type: string;
  status: string;
}

export interface CampaignStartResult {
  creator_id: string;
  sequences_scheduled: number;
  campaign_started_at: Date;
}

// 8-sequence email campaign for new creators
const EMAIL_SEQUENCES: EmailSequence[] = [
  {
    day: 0,
    type: 'welcome',
    subject: 'Welcome to Creator Platform',
    template: 'welcome'
  },
  {
    day: 1,
    type: 'getting_started',
    subject: 'Getting Started: Set Up Your First Publication',
    template: 'getting_started'
  },
  {
    day: 3,
    type: 'feature_highlight',
    subject: 'Discover: Advanced Analytics for Your Audience',
    template: 'feature_highlight'
  },
  {
    day: 7,
    type: 'success_story',
    subject: 'How Top Creators Are Growing (You Can Too)',
    template: 'success_story'
  },
  {
    day: 14,
    type: 'monetization_tips',
    subject: 'Monetization Tips: Turn Readers Into Revenue',
    template: 'monetization_tips'
  },
  {
    day: 21,
    type: 'community_feature',
    subject: 'Community Spotlight: Creator Success Stories',
    template: 'community_feature'
  },
  {
    day: 30,
    type: 'upgrade_offer',
    subject: 'Upgrade Offer: Premium Features at 50% Off',
    template: 'upgrade_offer'
  },
  {
    day: 45,
    type: 'retention',
    subject: 'We Miss You: Come Back and See What\'s New',
    template: 'retention'
  }
];

export const emailCampaignService = {
  /**
   * Get all email sequences in the campaign
   */
  getEmailSequences(): EmailSequence[] {
    return EMAIL_SEQUENCES;
  },

  /**
   * Start email campaign for a new creator
   */
  async startCampaign(creatorId: string): Promise<CampaignStartResult> {
    // Verify creator exists
    const creator = await prisma.creator.findUnique({
      where: { id: creatorId }
    });

    if (!creator) {
      throw new Error('Creator not found');
    }

    // Schedule all 8 emails
    const schedule = this.generateCampaignSchedule(creatorId);

    let scheduled = 0;
    for (const item of await schedule) {
      await this.createCampaignRecord({
        creator_id: creatorId,
        sequence_day: item.sequence_day,
        email_type: item.email_type,
        status: 'scheduled'
      });
      scheduled++;
    }

    return {
      creator_id: creatorId,
      sequences_scheduled: scheduled,
      campaign_started_at: new Date()
    };
  },

  /**
   * Generate email campaign schedule
   */
  async generateCampaignSchedule(creatorId: string): Promise<CampaignScheduleItem[]> {
    const creator = await prisma.creator.findUnique({
      where: { id: creatorId }
    });

    if (!creator) {
      throw new Error('Creator not found');
    }

    return EMAIL_SEQUENCES.map(seq => ({
      sequence_day: seq.day,
      email_type: seq.type,
      scheduled_date: new Date(Date.now() + seq.day * 24 * 60 * 60 * 1000)
    }));
  },

  /**
   * Create email campaign record
   */
  async createCampaignRecord(input: CreateCampaignRecordInput) {
    const creator = await prisma.creator.findUnique({
      where: { id: input.creator_id }
    });

    if (!creator) {
      throw new Error('Creator not found');
    }

    return prisma.emailCampaign.create({
      data: {
        creator_id: input.creator_id,
        sequence_day: input.sequence_day,
        email_type: input.email_type,
        status: input.status
      }
    });
  },

  /**
   * Get campaign history for a creator
   */
  async getCampaignHistory(creatorId: string) {
    return prisma.emailCampaign.findMany({
      where: { creator_id: creatorId },
      orderBy: { sequence_day: 'asc' }
    });
  },

  /**
   * Update email campaign status
   */
  async updateCampaignStatus(
    campaignId: string,
    status: 'scheduled' | 'sent' | 'failed' | 'bounced'
  ) {
    const data: any = { status };

    if (status === 'sent') {
      data.sent_at = new Date();
    }

    return prisma.emailCampaign.update({
      where: { id: campaignId },
      data
    });
  },

  /**
   * Track email open
   */
  async trackEmailOpen(campaignId: string) {
    return prisma.emailCampaign.update({
      where: { id: campaignId },
      data: { opened_at: new Date() }
    });
  },

  /**
   * Track email click
   */
  async trackEmailClick(campaignId: string) {
    return prisma.emailCampaign.update({
      where: { id: campaignId },
      data: { clicked_at: new Date() }
    });
  },

  /**
   * Send email via email service (mock for now)
   */
  async sendEmail(
    email: string,
    subject: string,
    template: string
  ): Promise<{ id: string; status: string }> {
    // This is a placeholder. In production, integrate with SendGrid, AWS SES, or similar
    const apiKey = process.env.SENDGRID_API_KEY || process.env.EMAIL_SERVICE_API_KEY;

    if (!apiKey) {
      throw new Error('Email service API key not configured');
    }

    // Simulated response (replace with actual email service call)
    return {
      id: `msg-${Date.now()}`,
      status: 'sent'
    };
  },

  /**
   * Get campaign metrics for a creator
   */
  async getCampaignMetrics(creatorId: string) {
    const campaigns = await prisma.emailCampaign.findMany({
      where: { creator_id: creatorId }
    });

    if (campaigns.length === 0) {
      return {
        creator_id: creatorId,
        total_sent: 0,
        total_opened: 0,
        total_clicked: 0,
        open_rate: 0,
        click_rate: 0
      };
    }

    const sent = campaigns.filter(c => c.status === 'sent').length;
    const opened = campaigns.filter(c => c.opened_at).length;
    const clicked = campaigns.filter(c => c.clicked_at).length;

    return {
      creator_id: creatorId,
      total_sent: sent,
      total_opened: opened,
      total_clicked: clicked,
      open_rate: sent > 0 ? (opened / sent) * 100 : 0,
      click_rate: sent > 0 ? (clicked / sent) * 100 : 0
    };
  }
};
