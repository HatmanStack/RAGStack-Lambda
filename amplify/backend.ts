import { defineBackend } from '@aws-amplify/backend';
import { auth } from './auth/resource';
import { data } from './data/resource';

/**
 * Amplify Gen 2 Backend - Auth and Data only
 *
 * Note: Web component CDN infrastructure (S3, CloudFront, CodeBuild) is managed
 * via SAM template (template.yaml) instead of Amplify backend to avoid
 * pipeline-deploy custom stack limitations.
 *
 * See docs/plans/ for migration details.
 *
 * @see https://docs.amplify.aws/react/build-a-backend/
 */
export const backend = defineBackend({
  auth,
  data,
});
