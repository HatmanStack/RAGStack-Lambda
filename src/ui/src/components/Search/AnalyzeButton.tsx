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
        <Alert type="error" dismissible onDismiss={() => {}}>
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

            <ColumnLayout columns={3} variant="text-grid">
              <div>
                <Box variant="awsui-key-label">Vectors Sampled</Box>
                <Box variant="awsui-value-large">{result.vectorsSampled.toLocaleString()}</Box>
              </div>
              <div>
                <Box variant="awsui-key-label">Keys Analyzed</Box>
                <Box variant="awsui-value-large">{result.keysAnalyzed}</Box>
              </div>
              <div>
                <Box variant="awsui-key-label">Examples Generated</Box>
                <Box variant="awsui-value-large">{result.examplesGenerated}</Box>
              </div>
            </ColumnLayout>

            <Box variant="p" color="text-body-secondary">
              The metadata statistics and filter examples have been updated. Refresh the page to
              see the latest data.
            </Box>
          </>
        )}
      </SpaceBetween>
    </Modal>
  );
};
