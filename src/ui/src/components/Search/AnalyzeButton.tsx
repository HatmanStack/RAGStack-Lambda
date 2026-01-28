import React, { useState } from 'react';
import {
  Button,
  Modal,
  Box,
  SpaceBetween,
  ColumnLayout,
  StatusIndicator,
  Alert,
} from '@cloudscape-design/components';
import { useMetadataAnalyzer, type MetadataAnalysisResult } from '../../hooks/useMetadata';

interface AnalyzeButtonProps {
  onComplete?: () => void;
}

export const AnalyzeButton: React.FC<AnalyzeButtonProps> = ({ onComplete }) => {
  const { analyze, analyzing, result, error } = useMetadataAnalyzer();
  const [showResult, setShowResult] = useState(false);

  const handleAnalyze = async () => {
    const analysisResult = await analyze();
    if (analysisResult) {
      setShowResult(true);
      if (onComplete) {
        onComplete();
      }
    }
  };

  const handleClose = () => {
    setShowResult(false);
  };

  return (
    <>
      <Button
        variant="primary"
        onClick={handleAnalyze}
        loading={analyzing}
        iconName="search"
        disabled={analyzing}
      >
        {analyzing ? 'Analyzing...' : 'Analyze Metadata'}
      </Button>

      {error && !showResult && (
        <Alert type="error">
          {error}
        </Alert>
      )}

      <AnalysisResultModal result={result} visible={showResult} onDismiss={handleClose} />
    </>
  );
};

interface AnalysisResultModalProps {
  result: MetadataAnalysisResult | null;
  visible: boolean;
  onDismiss: () => void;
}

const AnalysisResultModal: React.FC<AnalysisResultModalProps> = ({
  result,
  visible,
  onDismiss,
}) => {
  if (!result) return null;

  return (
    <Modal
      visible={visible}
      onDismiss={onDismiss}
      header="Metadata Analysis Complete"
      footer={
        <Button variant="primary" onClick={onDismiss}>
          Done
        </Button>
      }
    >
      <SpaceBetween size="l">
        {result.error ? (
          <Alert type="error">{result.error}</Alert>
        ) : (
          <>
            <StatusIndicator type="success">
              Analysis completed successfully in {(result.executionTimeMs / 1000).toFixed(1)}s
            </StatusIndicator>

            <ColumnLayout columns={2} variant="text-grid">
              <div>
                <Box variant="awsui-key-label">Vectors Sampled</Box>
                <Box variant="awsui-value-large">{result.vectorsSampled.toLocaleString()}</Box>
              </div>
              <div>
                <Box variant="awsui-key-label">Keys Discovered</Box>
                <Box variant="awsui-value-large">{result.keysAnalyzed}</Box>
              </div>
            </ColumnLayout>

            <Box variant="p" color="text-body-secondary">
              Metadata key statistics have been updated. To generate filter examples, select keys
              in the Filter Examples section and click "Regenerate Examples".
            </Box>
          </>
        )}
      </SpaceBetween>
    </Modal>
  );
};
