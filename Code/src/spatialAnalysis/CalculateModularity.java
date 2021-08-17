package spatialAnalysis;

import java.util.ArrayList;

import edu.sc.geography.regionalization.si.ExpectationSI_FLOW_Adjusted;
import edu.sc.geography.regionalization.si.MeasureSI_MODULARITY;

public class CalculateModularity {

	private String colnames[] = new String[] { "origin", "destination", "modularity", "rawvolume", "expectation" };
	private ArrayList<ModularityFlows> listModularityFlows = new ArrayList<ModularityFlows>();

	public CalculateModularity(float[][] flows, String locations[]) {

		ExpectationSI_FLOW_Adjusted ex = new ExpectationSI_FLOW_Adjusted();
		ex.setFlowData(flows, null);
		MeasureSI_MODULARITY m = new MeasureSI_MODULARITY();
		m.setData(ex);

		for (int a = 0; a < locations.length; a++) {
			for (int b = 0; b < locations.length; b++) {
				if (flows[a][b] > 0) {
					double betweenUnitFlow = flows[a][b];
					double expectation = ex.getBetweenUnitExpectation(a, b);
					double mod = m.calculateBetweenUnitMeasure(a, b);
					ModularityFlows mflows = new ModularityFlows(locations[a], locations[b], mod, betweenUnitFlow,
							expectation);
					listModularityFlows.add(mflows);
				}
			}
		}
	}

	public String[] getColnames() {
		return colnames;
	}

	public ArrayList<ModularityFlows> getFlowsNormalized() {
		return listModularityFlows;
	}

}
