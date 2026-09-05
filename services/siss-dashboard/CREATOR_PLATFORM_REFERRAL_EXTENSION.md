# Creator Platform Referral & Email Campaign Extension

## Overview
This document details the implementation of three key features to the Creator Platform MVP:
1. Substack OAuth2 Integration
2. Referral Tracking System (20% commission structure)
3. Email Campaign System (8-sequence nurture sequence)

**Target:** 100 creators by July 30, 2026

## Implementation Status
✅ All tests passing (27 unit tests)
✅ Core services implemented
✅ Database schema extended
✅ API routes created
✅ Dashboard UI components added

## 1. Substack OAuth2 Integration

### Files
- `lib/services/substack-authenticator.ts` - OAuth flow handler
- `app/api/auth/substack/callback/route.ts` - OAuth callback endpoint

### Features
- Authorization URL generation
- Code-to-token exchange
- User profile retrieval
- Token refresh capability
- Token validation

### Usage
```typescript
const authenticator = new SubstackAuthenticator();
const authUrl = authenticator.getAuthorizationUrl();
const tokens = await authenticator.exchangeCodeForToken(code);
const profile = await authenticator.getUserProfile(accessToken);
```

### Environment Variables
```
SUBSTACK_CLIENT_ID=your-client-id
SUBSTACK_CLIENT_SECRET=your-client-secret
SUBSTACK_REDIRECT_URI=http://localhost:3000/api/auth/substack/callback
```

## 2. Referral Tracking System

### Database Schema
```prisma
model Referral {
  id                    String      @id @default(uuid()) @db.Uuid
  referrer_id           String      @db.Uuid
  referred_creator_id   String      @db.Uuid
  commission_tier       String      // tier_1 (20%), tier_2 (15%), tier_3 (10%)
  amount                Decimal     @db.Decimal(12, 2)
  status                String      // pending, active, inactive
  created_at            DateTime    @default(now())
  updated_at            DateTime    @updatedAt

  referrer              Creator     @relation("referrer", fields: [referrer_id], references: [id], onDelete: Cascade)
  referred_creator      Creator     @relation("referred", fields: [referred_creator_id], references: [id], onDelete: Cascade)
}
```

### Commission Tiers
- **Tier 1:** 20% commission (default)
- **Tier 2:** 15% commission
- **Tier 3:** 10% commission

### Services
- `lib/services/referral.service.ts` - Core referral logic

### Key Methods
```typescript
// Calculate commission based on amount and tier
calculateCommission(amount: 1000, tier: 'tier_1'): number // Returns 200

// Create referral relationship
createReferral({
  referrer_id: string,
  referred_creator_id: string,
  commission_tier: 'tier_1' | 'tier_2' | 'tier_3',
  amount: number
}): Promise<Referral>

// Get all referrals for a creator
getReferrals(referrerId: string): Promise<Referral[]>

// Calculate total earnings from referrals
getReferralEarnings(referrerId: string): Promise<ReferralEarnings>

// Process commission when referral makes a sale
processReferralCommission(referredCreatorId: string, royaltyAmount: number)
```

### API Endpoints
- `POST /api/referrals` - Create new referral
- `GET /api/referrals?referrer_id=:id` - Get creator's referrals
- `GET /api/referrals/earnings?referrer_id=:id` - Get referral earnings

### UI Component
- `lib/components/ReferralEarningsDashboard.tsx` - Dashboard display

**Features:**
- Total commission earned display
- Referred creators count
- Referral table with tier indicators
- Real-time earnings calculation

## 3. Email Campaign System

### 8-Sequence Campaign Structure
```
Day 0:  Welcome Email
Day 1:  Getting Started: Set Up Your First Publication
Day 3:  Discover: Advanced Analytics for Your Audience
Day 7:  How Top Creators Are Growing (You Can Too)
Day 14: Monetization Tips: Turn Readers Into Revenue
Day 21: Community Spotlight: Creator Success Stories
Day 30: Upgrade Offer: Premium Features at 50% Off
Day 45: We Miss You: Come Back and See What's New
```

### Database Schema
```prisma
model EmailCampaign {
  id                String      @id @default(uuid()) @db.Uuid
  creator_id        String      @db.Uuid
  sequence_day      Int         // Day in the 8-sequence campaign
  email_type        String      // welcome, getting_started, etc.
  status            String      // scheduled, sent, failed, bounced
  sent_at           DateTime?
  opened_at         DateTime?
  clicked_at        DateTime?
  created_at        DateTime    @default(now())
  updated_at        DateTime    @updatedAt

  creator           Creator     @relation(fields: [creator_id], references: [id], onDelete: Cascade)
}
```

### Services
- `lib/services/email-campaign.service.ts` - Email campaign logic

### Key Methods
```typescript
// Get all email sequences
getEmailSequences(): EmailSequence[]

// Start campaign for a creator (schedules all 8 emails)
startCampaign(creatorId: string): Promise<CampaignStartResult>

// Generate schedule with dates
generateCampaignSchedule(creatorId: string): Promise<CampaignScheduleItem[]>

// Get campaign history and metrics
getCampaignHistory(creatorId: string)
getCampaignMetrics(creatorId: string)

// Track opens and clicks
trackEmailOpen(campaignId: string)
trackEmailClick(campaignId: string)
```

### API Endpoints
- `POST /api/email-campaigns/start` - Start campaign for creator
- `GET /api/email-campaigns/history?creator_id=:id` - Get campaign history and metrics

### UI Component
- `lib/components/EmailCampaignDashboard.tsx` - Campaign display

**Features:**
- Campaign sequence overview
- Email delivery status tracking
- Open rate and click rate metrics
- Start campaign button
- Email type labels with day schedule

## Integration Points

### OAuth Callback Flow
When a creator completes Substack OAuth:
1. Exchange auth code for tokens
2. Fetch creator profile from Substack
3. Create creator in system (or update existing)
4. **Automatically start email campaign** for new creators
5. **Process referral** if referrer ID included in state

### Royalty Integration
When a royalty is recorded:
1. Check if creator was referred
2. Calculate referral commission based on tier
3. Update referral amount in database
4. Display in referral earnings dashboard

## Test Coverage

### Unit Tests (27 tests - All Passing ✓)

**Substack OAuth Tests (8):**
- Authorization URL generation
- State parameter handling
- Code-to-token exchange
- User profile retrieval
- Error handling
- Token refresh
- Token validation

**Referral Tests (9):**
- 20% commission calculation
- 15% commission calculation
- 10% commission calculation
- Decimal amount handling
- Small and large amounts
- Tier ordering
- Precision handling

**Email Campaign Tests (10):**
- 8-sequence validation
- Correct day scheduling
- Unique email types
- Subject lines and templates
- Increasing days verification
- Welcome/retention email positioning
- Email spacing verification

## Migration Notes

### Database Changes
To apply the new schema:
```bash
npx prisma migrate dev --name add_referrals_email_campaigns
```

New tables created:
- `referrals` - Referral tracking
- `email_campaigns` - Email campaign tracking

## Performance Considerations

1. **Commission Calculation:** O(n) where n = completed royalties for referred creator
2. **Email Campaign:** Scheduled async sends, not blocking
3. **Indices on:**
   - `referrals.referrer_id`
   - `referrals.referred_creator_id`
   - `referrals.status`
   - `email_campaigns.creator_id`
   - `email_campaigns.status`
   - `email_campaigns.sequence_day`

## Security Considerations

1. **OAuth:** Uses secure code exchange, never exposes client secret in frontend
2. **Referral Validation:** Prevents self-referrals
3. **Commission Precision:** Uses Prisma Decimal for financial accuracy
4. **State Verification:** Validates state parameter in OAuth callback

## Future Enhancements

1. **Email Service Integration:** Connect to SendGrid, AWS SES, or Mailgun
2. **Dynamic Commission Tiers:** Based on performance or volume
3. **Referral Analytics:** Track conversion rates, engagement metrics
4. **A/B Testing:** Different email subject lines and content
5. **Webhook Support:** For email delivery status updates
6. **Referral Link Generation:** Unique tracking links per creator
7. **Commission Payouts:** Automatic settlement to referrer wallets

## Environment Variables Checklist

```
# Substack OAuth
SUBSTACK_CLIENT_ID=
SUBSTACK_CLIENT_SECRET=
SUBSTACK_REDIRECT_URI=http://localhost:3000/api/auth/substack/callback

# Email Service (future)
SENDGRID_API_KEY=
EMAIL_SERVICE_API_KEY=

# Database
DATABASE_URL=
```

## Testing Commands

```bash
# Run all unit tests
npm test -- tests/unit --run

# Run specific test
npm test -- tests/unit/referral-calculation.unit.test.ts --run

# Run with UI
npm test -- --ui

# Run specific test file pattern
npm test -- tests/unit/substack --run
```

## Deployment Checklist

- [ ] Environment variables configured
- [ ] Database migration applied
- [ ] All tests passing
- [ ] OAuth app created in Substack dashboard
- [ ] Email service credentials set
- [ ] Referral terms documented
- [ ] Commission payout process defined
- [ ] Email templates created/customized
- [ ] SSL certificate (for OAuth redirect)
