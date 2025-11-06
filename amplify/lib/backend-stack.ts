import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as appsync from 'aws-cdk-lib/aws-appsync';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import * as path from 'path';

export class AmplifyBackendStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Get required environment variables from SAM stack
    const kbId = process.env.KNOWLEDGE_BASE_ID;
    const configTableName = process.env.CONFIGURATION_TABLE_NAME;
    const samUserPoolId = process.env.USERPOOLID;
    const samUserPoolClientId = process.env.USERPOOLCLIENTID;

    if (!kbId || !configTableName || !samUserPoolId || !samUserPoolClientId) {
      throw new Error(
        'Required environment variables not set: KNOWLEDGE_BASE_ID, CONFIGURATION_TABLE_NAME, USERPOOLID, USERPOOLCLIENTID'
      );
    }

    // Create Cognito User Pool for Amplify-specific auth (optional - can use SAM's pool instead)
    // For now, we'll use the SAM stack's user pool to maintain compatibility
    const userPool = cognito.UserPool.fromUserPoolId(
      this,
      'ImportedUserPool',
      samUserPoolId
    );

    // Lambda Authorizer Function
    const authorizerFunction = new lambda.Function(this, 'AuthorizerFunction', {
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: 'authorizer.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../data/functions'), {
        bundling: {
          image: lambda.Runtime.NODEJS_20_X.bundlingImage,
          command: [
            'bash',
            '-c',
            'npm install && cp -r node_modules /asset-output/ && cp *.ts *.js /asset-output/ 2>/dev/null || true && cp ../config.ts /asset-output/ 2>/dev/null || true',
          ],
        },
      }),
      timeout: cdk.Duration.seconds(30),
      environment: {
        USER_POOL_ID: samUserPoolId,
        USER_POOL_CLIENT_ID: samUserPoolClientId,
        CONFIGURATION_TABLE_NAME: configTableName,
        AWS_NODEJS_CONNECTION_REUSE_ENABLED: '1',
      },
    });

    // Grant DynamoDB read permissions to authorizer
    authorizerFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['dynamodb:GetItem'],
        resources: [`arn:aws:dynamodb:${this.region}:${this.account}:table/${configTableName}`],
      })
    );

    // Create AppSync GraphQL API
    const api = new appsync.GraphqlApi(this, 'ChatApi', {
      name: `${id}-api`,
      definition: appsync.Definition.fromFile(path.join(__dirname, '../schema.graphql')),
      authorizationConfig: {
        defaultAuthorization: {
          authorizationType: appsync.AuthorizationType.LAMBDA,
          lambdaAuthorizerConfig: {
            handler: authorizerFunction,
            resultsCacheTtl: cdk.Duration.seconds(300),
          },
        },
        additionalAuthorizationModes: [
          {
            authorizationType: appsync.AuthorizationType.IAM,
          },
        ],
      },
      logConfig: {
        fieldLogLevel: appsync.FieldLogLevel.ERROR,
      },
      xrayEnabled: true,
    });

    // Conversation Query Lambda Resolver
    const conversationFunction = new lambda.Function(this, 'ConversationFunction', {
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: 'conversation.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../data/functions'), {
        bundling: {
          image: lambda.Runtime.NODEJS_20_X.bundlingImage,
          command: [
            'bash',
            '-c',
            'npm install && cp -r node_modules /asset-output/ && cp *.ts *.js /asset-output/ 2>/dev/null || true && cp ../config.ts /asset-output/ 2>/dev/null || true',
          ],
        },
      }),
      timeout: cdk.Duration.seconds(300),
      environment: {
        KNOWLEDGE_BASE_ID: kbId,
        CONFIGURATION_TABLE_NAME: configTableName,
        AWS_NODEJS_CONNECTION_REUSE_ENABLED: '1',
      },
    });

    // Grant Bedrock permissions to conversation function
    conversationFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          'bedrock:InvokeModel',
          'bedrock:RetrieveAndGenerate',
          'bedrock:Retrieve',
        ],
        resources: ['*'],
      })
    );

    // Grant DynamoDB read permissions to conversation function
    conversationFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['dynamodb:GetItem'],
        resources: [`arn:aws:dynamodb:${this.region}:${this.account}:table/${configTableName}`],
      })
    );

    // Create Lambda data source
    const conversationDataSource = api.addLambdaDataSource(
      'ConversationDataSource',
      conversationFunction
    );

    // Create resolver for conversation query
    conversationDataSource.createResolver('ConversationResolver', {
      typeName: 'Query',
      fieldName: 'conversation',
    });

    // Outputs for amplify_outputs.json generation
    new cdk.CfnOutput(this, 'GraphQLApiEndpoint', {
      value: api.graphqlUrl,
      exportName: `${id}-GraphQLApiEndpoint`,
    });

    new cdk.CfnOutput(this, 'GraphQLApiId', {
      value: api.apiId,
      exportName: `${id}-GraphQLApiId`,
    });

    new cdk.CfnOutput(this, 'GraphQLApiKey', {
      value: api.apiKey || 'none',
      exportName: `${id}-GraphQLApiKey`,
    });

    new cdk.CfnOutput(this, 'UserPoolId', {
      value: samUserPoolId,
      exportName: `${id}-UserPoolId`,
    });

    new cdk.CfnOutput(this, 'UserPoolClientId', {
      value: samUserPoolClientId,
      exportName: `${id}-UserPoolClientId`,
    });

    new cdk.CfnOutput(this, 'Region', {
      value: this.region,
      exportName: `${id}-Region`,
    });
  }
}
