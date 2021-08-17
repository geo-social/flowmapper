package servlet;

import java.io.IOException;
import java.io.PrintWriter;
import java.io.StringReader;
import java.util.ArrayList;
import java.util.Hashtable;

import javax.servlet.ServletException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

import org.supercsv.io.CsvBeanWriter;
import org.supercsv.io.ICsvBeanWriter;
import org.supercsv.prefs.CsvPreference;

import com.csvreader.CsvReader;

import spatialAnalysis.CalculateModularity;
import spatialAnalysis.ModularityFlows;

/**
 * Servlet implementation class FlowMapSl
 */
//@WebServlet("/FlowMapSl")
public class SpatialAnalysisSl extends HttpServlet {
	private static final long serialVersionUID = 1L;

	/**
	 * @see HttpServlet#HttpServlet()
	 */
	public SpatialAnalysisSl() {
		super();
		// TODO Auto-generated constructor stub
	}

	/**
	 * @see HttpServlet#doGet(HttpServletRequest request, HttpServletResponse
	 *      response)
	 */
	protected void doGet(HttpServletRequest request, HttpServletResponse response)
			throws ServletException, IOException {
		// TODO Auto-generated method stub
		response.getWriter().append("Served at: ").append(request.getContextPath());

	}

//	public class CsvWriter {
//
//	    public void writeCSV() {
//	        // File input path
//	        File file = new File("/home/Desktop/test/output.csv");
//	        try {
//	            FileWriter output = new FileWriter(file);
//	            CSVWriter write = new CSVWriter(output);
//
//	            // Header column value
//	            String[] header = { "ID", "Name", "Address", "Phone Number" };
//	            write.writeNext(header);
//	            // Value
//	            String[] data1 = { "1", "First Name", "Address1", "12345" };
//	            write.writeNext(data1);
//	            String[] data2 = { "2", "Second Name", "Address2", "123456" };
//	            write.writeNext(data2);
//	            String[] data3 = { "3", "Third Name", "Address3", "1234567" };
//	            write.writeNext(data3);
//	            write.close();
//	        } catch (Exception e) {
//	            // TODO: handle exception
//	            e.printStackTrace();
//
//	        }
//	    }
//	}

	public class Book {
		public String getTitle() {
			return title;
		}

		public void setTitle(String title) {
			this.title = title;
		}

		public String getDescription() {
			return description;
		}

		public void setDescription(String description) {
			this.description = description;
		}

		public String getAuthor() {
			return author;
		}

		public void setAuthor(String author) {
			this.author = author;
		}

		public String getPublisher() {
			return publisher;
		}

		public void setPublisher(String publisher) {
			this.publisher = publisher;
		}

		public String getIsbn() {
			return isbn;
		}

		public void setIsbn(String isbn) {
			this.isbn = isbn;
		}

		public String getPublishedDate() {
			return publishedDate;
		}

		public void setPublishedDate(String publishedDate) {
			this.publishedDate = publishedDate;
		}

		public float getPrice() {
			return price;
		}

		public void setPrice(float price) {
			this.price = price;
		}

		private String title;
		private String description;
		private String author;
		private String publisher;
		private String isbn;
		private String publishedDate;
		private float price;

		public Book() {
		}

		public Book(String title, String description, String author, String publisher, String isbn,
				String publishedDate, float price) {
			this.title = title;
			this.description = description;
			this.author = author;
			this.publisher = publisher;
			this.isbn = isbn;
			this.publishedDate = publishedDate;
			this.price = price;
		}

		// getters and setters...
	}

	/**
	 * @see HttpServlet#doPost(HttpServletRequest request, HttpServletResponse
	 *      response)
	 */
	protected void doPost(HttpServletRequest request, HttpServletResponse response)
			throws ServletException, IOException {
		// TODO Auto-generated method stub
//		doGet(request, response);

		String frontendData = request.getParameter("sentData");
		String type = request.getParameter("type");
		String toolName = request.getParameter("toolName");
		PrintWriter out = response.getWriter();

		Hashtable<String, Integer> nodehash = new Hashtable<String, Integer>();

		if (toolName.compareTo("normalizeFlows") == 0) {
			// parse the string to create the flow variable to store the data
			Object test = new StringReader(frontendData);
			CsvReader csvFile = new CsvReader(new StringReader(frontendData));
			System.out.println(csvFile.readHeaders());
			// check if there are three columns
			// TODO: csv data does not come through from frontend
			System.out.println(csvFile.getHeaderCount());
			System.out.println(csvFile.getColumnCount());

			if (csvFile.getHeaderCount() > 2) {
				csvFile.readHeaders();
				int locid = 0;
				ArrayList<Object[]> flowlist = new ArrayList<Object[]>();
				ArrayList<String> nodelist = new ArrayList<String>();

				while (csvFile.readRecord()) {
					String values[] = csvFile.getValues();
					String from = values[0];
					String to = values[1];
					float vol = Float.valueOf(values[2]);
					
					if(from != null && to!= null & vol > 0) {
						// pass the flows with integer ids into the modularity function.
						Integer fromid = nodehash.get(from);
						if (fromid == null) {
							nodelist.add(from);
							fromid = locid;
							nodehash.put(from, locid++);
						}
						Integer toid = nodehash.get(to);
						if (toid == null) {
							nodelist.add(to);
							toid = locid;
							nodehash.put(to, locid++);
						}
						flowlist.add(new Object[] { fromid, toid, vol });
					}
				}
				String locations[] = new String[nodelist.size()];
				for (int i = 0; i < nodelist.size(); i++) {
					locations[i] = nodelist.get(i);
				}
				float[][] flows = new float[nodelist.size()][nodelist.size()];
				for (int i = 0; i < flowlist.size(); i++) {
					Object[] flow = flowlist.get(i);
					int fromid = (int) flow[0];
					int toid = (int) flow[1];
					float vol = (float)flow[2];
					flows[fromid][toid] = vol;
				}

				CalculateModularity modularity = new CalculateModularity(flows, locations);

				String csvFileName = "modularityflows.csv";
				response.setContentType("text/csv");

				// creates mock data
				String headerKey = "Content-Disposition";
				String headerValue = String.format("attachment; filename=\"%s\"", csvFileName);
				response.setHeader(headerKey, headerValue);

				// uses the Super CSV API to generate CSV data from the model data
				ICsvBeanWriter csvWriter = new CsvBeanWriter(response.getWriter(), CsvPreference.STANDARD_PREFERENCE);

				String header[] = modularity.getColnames();
				csvWriter.writeHeader(header);

				ArrayList<ModularityFlows> listModularityFlows = modularity.getFlowsNormalized();
				for (ModularityFlows modflow : listModularityFlows) {
					csvWriter.write(modflow, header);
				}
				csvWriter.close();

			} else
				out.write("Error: There should be at least three columns in flow file: Origin, destination, volume");

		}

//		String csvFileName = "modularityflows.csv";
//		response.setContentType("text/csv");
//
//		// creates mock data
//		String headerKey = "Content-Disposition";
//		String headerValue = String.format("attachment; filename=\"%s\"", csvFileName);
//		response.setHeader(headerKey, headerValue);
//
//		Book book1 = new Book("Effective Java", "Java Best Practices", "Joshua Bloch", "Addision-Wesley", "0321356683",
//				"05/08/2008", 38);
//
//		Book book2 = new Book("Head First Java", "Java for Beginners", "Kathy Sierra & Bert Bates", "O'Reilly Media",
//				"0321356683", "02/09/2005", 30);
//
//		Book book3 = new Book("Thinking in Java", "Java Core In-depth", "Bruce Eckel", "Prentice Hall", "0131872486",
//				"02/26/2006", 45);
//
//		Book book4 = new Book("Java Generics and Collections", "Comprehensive guide to generics and collections",
//				"Naftalin & Philip Wadler", "O'Reilly Media", "0596527756", "10/24/2006", 27);
//
//		List<Book> listBooks = Arrays.asList(book1, book2, book3, book4);
//
//		// uses the Super CSV API to generate CSV data from the model data
//		ICsvBeanWriter csvWriter = new CsvBeanWriter(response.getWriter(), CsvPreference.STANDARD_PREFERENCE);
//
//		String[] header = { "Title", "Description", "Author", "Publisher", "isbn", "PublishedDate", "Price" };
//
//		csvWriter.writeHeader(header);
//
//		for (Book aBook : listBooks) {
//			csvWriter.write(aBook, header);
//		}
//
//		csvWriter.close();

//		if(type.equals("json")) {
//			out.write("Your input is a json file. It is not supported for network measurement.");
//		}else if(type.equals("csv")) {
//			CalculateNetworkMeasuresForWeb nm = new CalculateNetworkMeasuresForWeb(frontendData);
//			out.write(nm.outputString);
//		}
	}

	/*
	 * private void test(HttpServletRequest request, HttpServletResponse response)
	 * throws ServletException, IOException { String
	 * sentData=request.getParameter("sentData"); String type =
	 * request.getParameter("type"); PrintWriter out = response.getWriter();
	 * if(type.equals("json")) { JSONObject jsonObj = new JSONObject(sentData);
	 * JSONArray features = jsonObj.getJSONArray("features");
	 * System.out.println(features.length()); out.write("There are "+
	 * Integer.toString(features.length()) +" features in this json"); }else
	 * if(type.equals("csv")) { CsvReader products = new CsvReader(new
	 * StringReader(sentData)); products.readHeaders(); int resNum = 0; while
	 * (products.readRecord()) { String residence = products.get("residence");
	 * resNum = resNum + Integer.parseInt(residence); } out.write("There are "+
	 * resNum +" residence in this CSV");; } }
	 */

}
