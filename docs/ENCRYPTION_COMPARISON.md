# Encryption Configuration Comparison Report

## Repository Information

**Repository 1 (RAGStack-Lambda):**
- Location: `/root/RAGStack-Lambda/.worktrees/dt-worktree`
- Main template: `template.yaml` (1920 lines)
- Focus: Serverless OCR-to-Bedrock Knowledge Base pipeline

**Repository 2 (Base - Accelerated IDP):**
- Location: `/root/accelerated-intelligent-document-processing-on-aws`
- Main template: `template.yaml` (7000+ lines)
- Focus: Full-featured GenAI IDP solution with multiple patterns

---

## Encryption Configuration Summary by Service

### 1. S3 Bucket Encryption

#### RAGStack-Lambda (Repository 1)
**ALL S3 buckets use: AES256 (Server-Side Encryption)**

| Bucket | Encryption | KMS Key | Notes |
|--------|-----------|---------|-------|
| InputBucket | AES256 | None | Document uploads |
| OutputBucket | AES256 | None | Processed documents |
| WorkingBucket | AES256 | None | Temporary files |
| VectorBucket | AES256 | None | Embeddings/vectors |
| UIBucket | AES256 | None | Web UI assets |
| CloudTrailBucket | AES256 | None | Audit logging |

**File References:**
- Lines 96-99: InputBucket encryption
- Lines 127-130: OutputBucket encryption  
- Lines 165-168: WorkingBucket encryption
- Lines 192-195: VectorBucket encryption
- Lines 359-362: UIBucket encryption
- Lines 1664-1667: CloudTrailBucket encryption

#### Base Repository (Repository 2)
**Mixed encryption approach: AES256 + AWS KMS Customer Managed Key**

| Bucket | Encryption | KMS Key | Notes |
|--------|-----------|---------|-------|
| LoggingBucket | AES256 | None | S3 access logs destination |
| InputBucket | KMS | CustomerManagedEncryptionKey | Document uploads |
| OutputBucket | KMS | CustomerManagedEncryptionKey | Processed documents |
| RawDocumentBucket | KMS | CustomerManagedEncryptionKey | Raw document storage |
| ProcessedDataBucket | KMS | CustomerManagedEncryptionKey | Processed data |
| ReportingBucket | KMS | CustomerManagedEncryptionKey | Analytics/reporting |
| EvaluationBaselineBucket | KMS | CustomerManagedEncryptionKey | Evaluation baseline data |
| APILoggingBucket | KMS | CustomerManagedEncryptionKey | API access logs |

**KMS Key Definition (Base Repo):**
- Type: `AWS::KMS::Key` (line 1019)
- Key Rotation: Enabled (line 1031)
- Description: "KMS key for DynamoDB encryption"
- Alias: `alias/{StackName}-customer-encryption-key` (line 1092)

**File References:**
- Lines 1016-1087: CustomerManagedEncryptionKey definition
- Lines 1089-1093: CustomerManagedEncryptionKey alias
- Lines 1212-1213: InputBucket KMS encryption
- Lines 1279-1280: OutputBucket KMS encryption
- Lines 1346-1347: RawDocumentBucket KMS encryption
- Lines 1391-1392: ProcessedDataBucket KMS encryption

**Key Difference:** Base repo uses customer-managed KMS key for all data buckets; RAGStack-Lambda uses AWS managed AES256 encryption.

---

### 2. DynamoDB Encryption

#### RAGStack-Lambda (Repository 1)
**All DynamoDB tables use: AWS managed encryption (SSEEnabled: true, no KMS)**

| Table | SSE Enabled | Encryption Type | KMS Key |
|-------|-----------|-----------------|---------|
| TrackingTable | Yes | Default (AWS managed) | None |
| MeteringTable | Yes | Default (AWS managed) | None |
| ConfigurationTable | Yes | Default (AWS managed) | None |

**Configuration:**
```yaml
SSESpecification:
  SSEEnabled: true
```

**File References:**
- Lines 461-462: TrackingTable SSE
- Lines 504-505: MeteringTable SSE
- Lines 538-539: ConfigurationTable SSE

#### Base Repository (Repository 2)
**All DynamoDB tables use: Customer-managed KMS encryption**

| Table | SSE Enabled | Encryption Type | KMS Key |
|-------|-----------|-----------------|---------|
| Document table | Yes | KMS | CustomerManagedEncryptionKey |
| Reporting table | Yes | KMS | CustomerManagedEncryptionKey |
| OpenSearch backup | Yes | KMS | CustomerManagedEncryptionKey |
| Configuration table | Yes | KMS | CustomerManagedEncryptionKey |
| All other tables | Yes | KMS | CustomerManagedEncryptionKey |

**Configuration Example:**
```yaml
SSESpecification:
  SSEEnabled: true
  SSEType: KMS
  KMSMasterKeyId: !Ref CustomerManagedEncryptionKey
```

**File References:**
- Line 2052-2054: DynamoDB SSE with KMS
- Line 2077-2079: Additional DynamoDB KMS encryption
- Line 2149-2151: Further DynamoDB KMS encryption
- Line 2173-2175: Additional DynamoDB KMS encryption

**Key Difference:** Base repo uses customer-managed KMS for all DynamoDB tables; RAGStack-Lambda uses AWS managed default encryption.

---

### 3. SQS Queue Encryption

#### RAGStack-Lambda (Repository 1)
**SQS Queue uses: SQS-managed SSE**

| Queue | Encryption | Details |
|-------|-----------|---------|
| ProcessingDLQ | SqsManagedSseEnabled: true | AWS managed encryption |

**Configuration (Line 1390):**
```yaml
SqsManagedSseEnabled: true
```

#### Base Repository (Repository 2)
**SQS Queues use: Customer-managed KMS encryption**

| Queue | Encryption | KMS Key |
|-------|-----------|---------|
| DiscoveryQueue | KMS | CustomerManagedEncryptionKey |
| DiscoveryDLQ | KMS | CustomerManagedEncryptionKey |
| ConfigurationQueue | KMS | CustomerManagedEncryptionKey |
| ConfigurationDLQ | KMS | CustomerManagedEncryptionKey |
| DocumentQueue | KMS | CustomerManagedEncryptionKey |
| DocumentDLQ | KMS | CustomerManagedEncryptionKey |

**Configuration Example:**
```yaml
KmsMasterKeyId: !Ref CustomerManagedEncryptionKey
```

**File References:**
- Lines 2330-2350: DiscoveryQueue with KMS
- Lines 2360-2375: ConfigurationQueue with KMS
- Lines 2385-2400: DocumentQueue definitions

**Key Difference:** Base repo uses customer-managed KMS; RAGStack-Lambda uses SQS-managed encryption.

---

### 4. SNS Topic Encryption

#### RAGStack-Lambda (Repository 1)
**SNS Topic uses: AWS managed encryption (alias/aws/sns)**

| Resource | Encryption | KMS Key | Details |
|----------|-----------|---------|---------|
| AlarmTopic | KMS | alias/aws/sns | AWS managed key |

**Configuration (Line 1401):**
```yaml
KmsMasterKeyId: alias/aws/sns
```

#### Base Repository (Repository 2)
**SNS Topic uses: Customer-managed KMS encryption**

| Resource | Encryption | KMS Key | Details |
|----------|-----------|---------|---------|
| AlertsTopic | KMS | CustomerManagedEncryptionKey | Customer managed |

**Configuration (Line 3014-3015):**
```yaml
KmsMasterKeyId: !Ref CustomerManagedEncryptionKey
```

**Key Difference:** RAGStack-Lambda uses AWS managed key for SNS; base repo uses customer-managed key.

---

### 5. CodeBuild Encryption

#### RAGStack-Lambda (Repository 1)
**CodeBuild Project uses: AWS managed S3 encryption**

| Resource | Encryption Key | Details |
|----------|-------------|---------|
| UICodeBuildProject | alias/aws/s3 | AWS managed for artifact encryption |

**Configuration (Line 293):**
```yaml
EncryptionKey: alias/aws/s3
```

#### Base Repository (Repository 2)
**CodeBuild Project uses: AWS managed S3 encryption**

| Resource | Encryption Key | Details |
|----------|-------------|---------|
| UICodeBuildProject | alias/aws/s3 | AWS managed for artifact encryption |

**Configuration:**
```yaml
EncryptionKey: alias/aws/s3
```

**Key Difference:** Both repositories use AWS managed encryption for CodeBuild - **NO DIFFERENCE**.

---

### 6. Other Services Encryption Status

#### Lambda Functions
- **RAGStack-Lambda:** No explicit encryption configuration (uses service defaults)
- **Base Repository:** No explicit encryption configuration (uses service defaults)
- **Tracing:** Both enable X-Ray tracing (Active)

#### Cognito
- **RAGStack-Lambda:** No explicit encryption configuration
- **Base Repository:** No explicit encryption configuration
- Both use standard Cognito encryption at rest

#### AppSync GraphQL API
- **RAGStack-Lambda:** No explicit encryption configuration
- **Base Repository:** No explicit encryption configuration
- Both use standard AppSync encryption

#### CloudFront Distribution
- **RAGStack-Lambda:** HTTPS enforced, CloudFrontDefaultCertificate
- **Base Repository:** HTTPS enforced via ViewerCertificate configuration
- **Note:** CloudFront automatically encrypts in-transit; no at-rest encryption configuration in both

#### CloudWatch Logs
- **RAGStack-Lambda:** No explicit KMS encryption for log groups
- **Base Repository:** No explicit KMS encryption for most log groups
- **Note:** Log groups can be encrypted with KMS but neither repo implements this

#### CloudTrail
- **RAGStack-Lambda:** Uses S3 bucket with AES256 encryption (line 1664)
- **Base Repository:** Uses S3 bucket with KMS encryption

---

## KMS Key Management Summary

### RAGStack-Lambda (Repository 1)
- **Custom KMS Key Created:** NO
- **AWS Managed Keys Used:** YES (alias/aws/s3, alias/aws/sns)
- **Key Rotation:** Not applicable (AWS managed keys auto-rotate)
- **KMS Key Count:** 0 customer-managed keys

### Base Repository (Repository 2)
- **Custom KMS Key Created:** YES
- **Customer Managed Key Properties:**
  - Type: `AWS::KMS::Key`
  - Key Rotation: Enabled (line 1031: `EnableKeyRotation: true`)
  - Alias: `alias/{StackName}-customer-encryption-key`
  - Services with access:
    - DynamoDB
    - CloudWatch Logs
    - Lambda functions
    - S3 services (for S3 Vectors)
    - CloudTrail
    - SQS
    - SNS
    - Glue (for S3 encryption mode)

**Key Policy Summary (Base Repo):**
- **Principal 1:** Account root (IAM User Permissions)
  - Actions: `kms:*`
  - Resource: `*`

- **Principal 2:** DynamoDB service
  - Actions: Encrypt, Decrypt, ReEncrypt, GenerateDataKey, DescribeKey
  - Resource: `*`

- **Principal 3:** CloudWatch Logs service
  - Actions: Encrypt, Decrypt, ReEncrypt, GenerateDataKey, DescribeKey
  - Resource: `*`

- **Principal 4:** S3 Vectors (conditional on IsS3VectorsVectorStore)
  - Actions: Encrypt, Decrypt, ReEncrypt, GenerateDataKey, DescribeKey
  - Resource: `*`

**File References (Base Repo KMS):**
- Line 1016: CustomerManagedEncryptionKey definition
- Line 1019: Type: AWS::KMS::Key
- Line 1030: Description
- Line 1031: EnableKeyRotation: true
- Lines 1032-1087: KeyPolicy configuration

---

## Comparison Table - All Services

| Service | RAGStack-Lambda | Base Repository | Difference |
|---------|----------------|-----------------|-----------|
| **S3 Buckets** | AES256 | KMS (CMK) | Base uses stronger encryption |
| **DynamoDB** | AWS managed SSE | KMS (CMK) | Base uses customer-managed keys |
| **SQS** | SQS-managed SSE | KMS (CMK) | Base uses customer-managed keys |
| **SNS** | alias/aws/sns (AWS managed) | KMS (CMK) | Base uses customer-managed key |
| **CodeBuild** | alias/aws/s3 | alias/aws/s3 | Same (AWS managed) |
| **Lambda** | Default | Default | Same |
| **Cognito** | Default | Default | Same |
| **AppSync** | Default | Default | Same |
| **CloudFront** | HTTPS only | HTTPS only | Same |
| **CloudWatch Logs** | Not encrypted with KMS | Some encrypted with KMS | Base has more encryption |
| **CloudTrail** | AES256 | KMS (CMK) | Base uses customer-managed key |
| **Custom KMS Key** | NO (0 keys) | YES (1 CMK) | Base has key management overhead |

---

## Security Implications

### RAGStack-Lambda Approach (AWS Managed Encryption)
**Strengths:**
- Simpler management - no KMS key to manage or rotate
- Lower operational overhead
- AWS handles key management automatically
- Suitable for less sensitive workloads
- No additional AWS KMS costs

**Weaknesses:**
- Cannot audit access to keys
- No control over who can decrypt data
- Cannot rotate keys manually
- May not meet compliance requirements
- Less granular access control

### Base Repository Approach (Customer-Managed KMS)
**Strengths:**
- Full control over encryption keys
- Manual key rotation possible (though auto-rotation enabled)
- Audit access to keys via CloudTrail
- Fine-grained access control per service
- Meets strict compliance requirements (HIPAA, PCI-DSS, etc.)
- Can implement key policies with additional conditions

**Weaknesses:**
- Operational overhead - must manage KMS keys
- Additional AWS costs (KMS API calls, key storage)
- Risk of key deletion or accidental lock-out
- Must ensure proper key policy configuration
- Complexity in multi-account scenarios

---

## Recommendations for RAGStack-Lambda

### If Enhanced Security is Required:

1. **Create Customer-Managed KMS Key:**
   ```yaml
   CustomerManagedEncryptionKey:
     Type: AWS::KMS::Key
     Properties:
       Description: RAGStack encryption key
       EnableKeyRotation: true
       KeyPolicy:
         Version: '2012-10-17'
         Statement:
           - Sid: Enable IAM permissions
             Effect: Allow
             Principal:
               AWS: !Sub 'arn:${AWS::Partition}:iam::${AWS::AccountId}:root'
             Action: 'kms:*'
             Resource: '*'
           - Sid: Allow services
             Effect: Allow
             Principal:
               Service:
                 - dynamodb.amazonaws.com
                 - s3.amazonaws.com
                 - sqs.amazonaws.com
                 - sns.amazonaws.com
             Action:
               - 'kms:Decrypt'
               - 'kms:GenerateDataKey'
               - 'kms:DescribeKey'
             Resource: '*'
   ```

2. **Update S3 buckets:** Change `SSEAlgorithm: AES256` to `SSEAlgorithm: aws:kms` with KMS key reference

3. **Update DynamoDB tables:** Add `SSEType: KMS` and `KMSMasterKeyId` references

4. **Update SQS queues:** Replace `SqsManagedSseEnabled: true` with `KmsMasterKeyId` reference

5. **Update SNS topics:** Replace `alias/aws/sns` with customer-managed key reference

---

## Compliance Considerations

| Requirement | RAGStack-Lambda | Base Repository | Notes |
|------------|-----------------|-----------------|-------|
| AWS Config | Not enforced | Likely supported | Need to check config |
| CloudTrail audit | Limited | Full audit trail | KMS operations logged |
| HIPAA | Weak support | Strong support | CMK required |
| PCI-DSS | Weak support | Strong support | CMK required |
| SOC2 | Moderate | Strong | CMK recommended |
| GDPR | Adequate | Strong | Encryption at rest needed |
| Custom compliance | Not supported | Supported | Key policies customizable |

---

## Cost Analysis

### RAGStack-Lambda (AWS Managed)
- S3 encryption: No additional cost (included in S3 pricing)
- DynamoDB encryption: No additional cost (included in pricing)
- SQS encryption: No additional cost (included in pricing)
- SNS encryption: No additional cost (included in pricing)
- **Total KMS costs: $0/month**

### Base Repository (Customer-Managed KMS)
- KMS key storage: $1.00/month
- KMS API requests: ~$0.03 per 10,000 requests
- **Estimated monthly KMS costs: $1-50 depending on usage**
- DynamoDB/S3 operations: Minimal increase from KMS calls

---

## Summary

**Key Takeaways:**

1. **Encryption Strategy:** RAGStack-Lambda uses simpler AWS-managed encryption; base repo uses customer-managed KMS throughout

2. **Security Level:** Base repository provides stronger security posture suitable for enterprise/sensitive workloads

3. **Operational Complexity:** RAGStack-Lambda is simpler; base repo requires KMS key management

4. **Compliance:** Base repository better suited for regulated industries; RAGStack-Lambda adequate for standard workloads

5. **Cost:** RAGStack-Lambda has minimal encryption costs; base repo incurs KMS charges

6. **No Major Red Flags:** Neither repository has critical encryption vulnerabilities; it's a design choice between simplicity vs. control
