-- CreateTable Creators
CREATE TABLE "creators" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "name" VARCHAR(255) NOT NULL,
    "email" VARCHAR(255) NOT NULL,
    "wallet" VARCHAR(42) NOT NULL,
    "stripe_customer_id" VARCHAR(255) NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "creators_pkey" PRIMARY KEY ("id")
);

-- CreateTable Royalties
CREATE TABLE "royalties" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "creator_id" UUID NOT NULL,
    "amount" DECIMAL(12,2) NOT NULL,
    "fee_percentage" DECIMAL(5,2) NOT NULL DEFAULT 5.0,
    "net_amount" DECIMAL(12,2) NOT NULL,
    "timestamp" TIMESTAMP(3) NOT NULL,
    "status" VARCHAR(255) NOT NULL DEFAULT 'pending',
    "webhook_event_id" VARCHAR(255),
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "royalties_pkey" PRIMARY KEY ("id")
);

-- CreateTable Settlements
CREATE TABLE "settlements" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "batch_id" VARCHAR(255) NOT NULL,
    "creator_ids" TEXT[],
    "total_amount" DECIMAL(12,2) NOT NULL,
    "tx_hash" VARCHAR(255),
    "status" VARCHAR(255) NOT NULL DEFAULT 'pending',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "settled_at" TIMESTAMP(3),

    CONSTRAINT "settlements_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "creators_email_key" ON "creators"("email");

-- CreateIndex
CREATE UNIQUE INDEX "creators_wallet_key" ON "creators"("wallet");

-- CreateIndex
CREATE INDEX "creators_email_idx" ON "creators"("email");

-- CreateIndex
CREATE INDEX "creators_wallet_idx" ON "creators"("wallet");

-- CreateIndex
CREATE INDEX "royalties_creator_id_idx" ON "royalties"("creator_id");

-- CreateIndex
CREATE INDEX "royalties_status_idx" ON "royalties"("status");

-- CreateIndex
CREATE INDEX "royalties_timestamp_idx" ON "royalties"("timestamp");

-- CreateIndex
CREATE UNIQUE INDEX "royalties_webhook_event_id_key" ON "royalties"("webhook_event_id");

-- CreateIndex
CREATE INDEX "royalties_webhook_event_id_idx" ON "royalties"("webhook_event_id");

-- CreateIndex
CREATE INDEX "settlements_status_idx" ON "settlements"("status");

-- CreateIndex
CREATE UNIQUE INDEX "settlements_batch_id_key" ON "settlements"("batch_id");

-- CreateIndex
CREATE INDEX "settlements_batch_id_idx" ON "settlements"("batch_id");

-- AddForeignKey
ALTER TABLE "royalties" ADD CONSTRAINT "royalties_creator_id_fkey" FOREIGN KEY ("creator_id") REFERENCES "creators"("id") ON DELETE CASCADE ON UPDATE CASCADE;
