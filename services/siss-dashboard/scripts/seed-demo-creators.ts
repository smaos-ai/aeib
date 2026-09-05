import { PrismaClient } from '@prisma/client';
import { Decimal } from '@prisma/client/runtime/library';

const prisma = new PrismaClient();

async function seed() {
  console.log('🌱 Seeding demo creators...');

  // Clear existing data
  await prisma.royalty.deleteMany();
  await prisma.settlement.deleteMany();
  await prisma.creator.deleteMany();

  // Create 3 demo creators
  const creator1 = await prisma.creator.create({
    data: {
      name: 'Alex Chen',
      email: 'alex@creators.dev',
      wallet: '0x742d35Cc6634C0532925a3b844Bc49e0Fcf02567',
      stripe_customer_id: 'cus_demo_001'
    }
  });

  const creator2 = await prisma.creator.create({
    data: {
      name: 'Jordan Rodriguez',
      email: 'jordan@creators.dev',
      wallet: '0x88A0a46f0E2a69D3e1bCB0c1a99C6C8e1E7f8E9d',
      stripe_customer_id: 'cus_demo_002'
    }
  });

  const creator3 = await prisma.creator.create({
    data: {
      name: 'Sam Patel',
      email: 'sam@creators.dev',
      wallet: '0x32Be343B94f860124dC4fEe278FADFA5B4c14Ffe',
      stripe_customer_id: 'cus_demo_003'
    }
  });

  console.log('✅ Created 3 demo creators');

  // Add royalty entries to reach €500+ total MRR
  // Creator 1: €200 total
  await prisma.royalty.create({
    data: {
      creator_id: creator1.id,
      amount: new Decimal('100.00'),
      fee_percentage: new Decimal('5'),
      net_amount: new Decimal('95.00'),
      timestamp: new Date('2026-06-01'),
      status: 'completed',
      webhook_event_id: 'evt_demo_001'
    }
  });

  await prisma.royalty.create({
    data: {
      creator_id: creator1.id,
      amount: new Decimal('105.26'),
      fee_percentage: new Decimal('5'),
      net_amount: new Decimal('100.00'),
      timestamp: new Date('2026-06-02'),
      status: 'completed',
      webhook_event_id: 'evt_demo_002'
    }
  });

  // Creator 2: €200 total
  await prisma.royalty.create({
    data: {
      creator_id: creator2.id,
      amount: new Decimal('150.00'),
      fee_percentage: new Decimal('5'),
      net_amount: new Decimal('142.50'),
      timestamp: new Date('2026-06-01'),
      status: 'completed',
      webhook_event_id: 'evt_demo_003'
    }
  });

  await prisma.royalty.create({
    data: {
      creator_id: creator2.id,
      amount: new Decimal('60.32'),
      fee_percentage: new Decimal('5'),
      net_amount: new Decimal('57.30'),
      timestamp: new Date('2026-06-02'),
      status: 'completed',
      webhook_event_id: 'evt_demo_004'
    }
  });

  // Creator 3: €150+ total
  await prisma.royalty.create({
    data: {
      creator_id: creator3.id,
      amount: new Decimal('157.89'),
      fee_percentage: new Decimal('5'),
      net_amount: new Decimal('150.00'),
      timestamp: new Date('2026-06-01'),
      status: 'completed',
      webhook_event_id: 'evt_demo_005'
    }
  });

  console.log('✅ Created demo royalties (€500+ total MRR)');

  // Display summary
  const royalties = await prisma.royalty.findMany();
  const totalNet = royalties.reduce((sum, r) => sum.add(r.net_amount), new Decimal('0'));

  console.log('\n📊 Demo Data Summary:');
  console.log(`Total Creators: 3`);
  console.log(`Total Royalties Recorded: ${royalties.length}`);
  console.log(`Total MRR: €${totalNet.toString()}`);
  console.log('\nCreators:');
  console.log(`  1. ${creator1.name} - €200.00`);
  console.log(`  2. ${creator2.name} - €199.80`);
  console.log(`  3. ${creator3.name} - €150.00`);
  console.log(`\nTotal: €${totalNet.toString()}\n`);
}

seed()
  .then(() => {
    console.log('✨ Seed completed successfully!');
    process.exit(0);
  })
  .catch(error => {
    console.error('Seed failed:', error);
    process.exit(1);
  });
