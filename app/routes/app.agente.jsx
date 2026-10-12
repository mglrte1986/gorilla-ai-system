import { Page, Layout, Card, BlockStack, Text, Button } from "@shopify/polaris";

export default function AgentePage() {
  return (
    <Page title="Centro de Mando - Rodamaster Agente">
      <Layout>
        <Layout.Section>
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">
                Acciones Operativas
              </Text>
              <Text as="p">
                Panel de control para tareas automáticas de catálogo y cobros.
              </Text>
              <Button variant="primary">
                Auditar Catálogo CSV
              </Button>
              <Button>
                Generar Links de Venta
              </Button>
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
