/* Matkon: which aisle a shopping-list item is in, by its words (English and Hebrew).
   window.MatkonAisles.of("cherry tomatoes") → "produce". The longest word that matches wins, so "black pepper"
   is a spice and "pepper" is produce. A person's own choice for an item (memory.aisles) comes first, in app.js.
   The same table as the Android app. */
(function () {
  "use strict";
  const ORDER = ["produce", "bakery", "meat", "dairy", "frozen", "pantry", "spices", "drinks", "household", "other"];
  const NAMES = { produce: "Produce", bakery: "Bakery", meat: "Meat and fish", dairy: "Dairy and eggs", frozen: "Frozen",
    pantry: "Pantry", spices: "Spices", drinks: "Drinks", household: "Household", other: "Other" };
  const WORDS = {
    produce: "apple banana lemon lime orange grapefruit tomato tomatoes onion onions garlic ginger potato potatoes carrot carrots celery cucumber cucumbers " +
      "bell pepper peppers chili chilli chilies jalapeno jalapeño serrano lettuce romaine spinach kale arugula rocket cabbage broccoli cauliflower " +
      "zucchini courgette eggplant aubergine mushroom mushrooms avocado corn peas green beans parsley cilantro fresh coriander dill mint basil " +
      "rosemary fresh thyme scallion scallions spring onion spring onions green onion leek shallot shallots beet beets radish radishes squash pumpkin " +
      "berries strawberries strawberry blueberries raspberries grapes mango pineapple pomegranate fig figs peach pear watermelon melon cherry tomatoes " +
      "chives fennel asparagus bok choy sprouts microgreens herbs lemongrass kohlrabi artichoke okra sweet potato yam " +
      "עגבניה עגבניות עגבניות שרי בצל בצלים שום ג׳ינג׳ר ג'ינג'ר תפוח אדמה תפוחי אדמה תפו״א גזר סלרי מלפפון מלפפונים פלפל פלפלים גמבה צ׳ילי צ'ילי " +
      "חסה תרד קייל כרוב ברוקולי כרובית קישוא קישואים חציל חצילים פטריות פטריה אבוקדו תירס אפונה שעועית ירוקה פטרוזיליה כוסברה שמיר נענע " +
      "בזיליקום רוזמרין טימין טרי בצל ירוק כרישה שאלוט סלק צנון דלעת לימון ליים תפוז תפוח תפוחים בננה בטטה רימון מנגו אננס תאנים ענבים " +
      "תותים פירות יער אוכמניות אגס אפרסק אבטיח מלון עירית שומר אספרגוס עשבי תיבול",
    bakery: "bread pita pitas baguette bun buns rolls tortilla tortillas wrap wraps croissant croissants bagel bagels challah lafa sourdough brioche " +
      "flatbread naan english muffins לחם פיתה פיתות לאפה חלה בגט טורטיה טורטיות לחמניה לחמניות בייגל קרואסון",
    meat: "chicken chicken breast chicken thighs beef ground beef lamb ground lamb pork turkey ground meat mince minced meat steak sausage sausages " +
      "bacon salmon fish shrimp prawns sardines cod tilapia sea bass trout anchovies tuna steak brisket ribs veal duck kebab meatballs " +
      "עוף חזה עוף חזה פרגית פרגיות שוקיים כרעיים בשר בשר טחון טחון כבש הודו נקניק נקניקיות סלמון דג דגים שרימפס סרדינים אנטריקוט " +
      "בריסקט צלעות קבב כבד אמנון דניס לברק",
    dairy: "milk butter cheese cream heavy cream whipping cream sour cream cream cheese yogurt yoghurt greek yogurt labneh feta mozzarella burrata parmesan " +
      "parmigiano pecorino ricotta cheddar gruyere halloumi goat cheese cottage cheese buttermilk ghee mascarpone egg eggs egg yolks egg whites " +
      "חלב חמאה גבינה גבינות שמנת שמנת מתוקה שמנת חמוצה גבינת שמנת יוגורט לבנה פטה בולגרית מוצרלה פרמזן ריקוטה צ׳דר חלומי גבינת עיזים קוטג׳ " +
      "קוטג' מסקרפונה ביצה ביצים חלמונים חלבונים",
    frozen: "frozen ice cream puff pastry frozen peas frozen spinach phyllo filo קפוא קפואה קפואים גלידה בצק עלים בצק פילו",
    pantry: "flour all-purpose flour bread flour sugar brown sugar powdered sugar icing sugar rice basmati pasta spaghetti penne noodles ramen noodles " +
      "oil olive oil vegetable oil canola oil sesame oil vinegar balsamic soy sauce tamari honey maple syrup date syrup silan tahini tomato paste " +
      "canned tomatoes crushed tomatoes tomato sauce passata beans chickpeas lentils stock broth bouillon chicken stock vegetable stock chicken broth vegetable broth beef stock beef broth fish stock miso peanut butter jam chocolate " +
      "chocolate chips cocoa baking powder baking soda yeast oats breadcrumbs panko nuts almonds walnuts pecans pistachios cashews pine nuts " +
      "raisins dates sesame seeds sesame mustard ketchup mayonnaise mayo sriracha harissa hot sauce couscous bulgur quinoa semolina cornstarch " +
      "corn starch gelatin coconut milk coconut cream coconut canned tuna capers olives pickles fish sauce oyster sauce hoisin gochujang " +
      "vanilla extract matzah crackers cereal granola " +
      "קמח קמח לבן סוכר סוכר חום אבקת סוכר אורז פסטה ספגטי אטריות שמן שמן זית שמן קנולה שמן שומשום חומץ בלסמי רוטב סויה סויה דבש סילאן " +
      "סירופ מייפל טחינה רסק עגבניות רסק עגבניות מרוסקות שימורים שעועית חומוס גרגרי חומוס עדשים ציר אבקת מרק מיסו חמאת בוטנים ריבה שוקולד " +
      "שוקולד צ׳יפס קקאו אבקת אפייה סודה לשתייה שמרים שיבולת שועל פירורי לחם פנקו אגוזים שקדים אגוזי מלך פקאן פיסטוק קשיו צנוברים צימוקים " +
      "תמרים שומשום חרדל קטשופ מיונז הריסה סחוג קוסקוס בורגול קינואה סולת קורנפלור ג׳לטין חלב קוקוס קרם קוקוס טונה זיתים ירקות כבושים " +
      "מצה מצות קרקרים",
    spices: "salt and pepper salt kosher salt sea salt black pepper pepper flakes red pepper flakes chili flakes paprika smoked paprika sweet paprika cumin turmeric " +
      "cinnamon nutmeg cardamom allspice baharat za'atar zaatar sumac dried oregano oregano chili powder cayenne curry powder garam masala " +
      "bay leaf bay leaves ground coriander coriander seeds cloves ground ginger garlic powder onion powder saffron dried thyme thyme " +
      "fennel seeds mustard seeds seasoning everything bagel seasoning hawaij ras el hanout five spice star anise " +
      "מלח מלח גס פלפל שחור פפריקה פפריקה מעושנת פפריקה מתוקה כמון כורכום קינמון אגוז מוסקט הל פלפל אנגלי בהרט זעתר סומק אורגנו " +
      "צ׳ילי גרוס צ'ילי גרוס פלפל חריף גרוס קארי עלי דפנה כוסברה טחונה ציפורן שום גבישי אבקת שום אבקת בצל זעפרן חוואייג׳ ראס אל חנות תבלין תבלינים",
    drinks: "wine white wine red wine beer juice orange juice coffee espresso tea soda sparkling water club soda " +
      "יין יין לבן יין אדום בירה מיץ מיץ תפוזים קפה אספרסו תה סודה מים מוגזים",
    household: "foil aluminum foil parchment parchment paper baking paper paper towels napkins toothpicks skewers plastic wrap zip bags " +
      "נייר אפייה נייר כסף מגבות נייר מפיות קיסמים שיפודים ניילון נצמד שקיות",
  };
  const norm = (s) => String(s || "").toLowerCase().normalize("NFKD").replace(/\p{M}+/gu, "").replace(/['׳״"]/g, "").replace(/[^\p{L}\p{N} -]+/gu, " ").replace(/\s+/g, " ").trim();
  // every phrase of one to three words in each list, longest first ("black pepper" before "pepper")
  const PHRASES = [];
  for (const [aisle, words] of Object.entries(WORDS)) {
    const ws = words.split(" ");
    const seen = new Set();
    for (let n = 3; n >= 1; n--) {
      for (let i = 0; i + n <= ws.length; i++) {
        const p = norm(ws.slice(i, i + n).join(" "));
        if (!seen.has(p)) { seen.add(p); PHRASES.push([p, aisle]); }
      }
    }
  }
  // joining neighbours in a list makes false phrases ("sugar rice"): a phrase of two or more words counts
  // only when it's one of these
  const REAL = new Set();
  const KNOWN = [
    "bell pepper", "green beans", "fresh coriander", "fresh thyme", "spring onion", "spring onions", "green onion", "cherry tomatoes", "bok choy", "sweet potato",
    "chicken breast", "chicken thighs", "ground beef", "ground lamb", "ground meat", "minced meat", "sea bass", "tuna steak", "heavy cream", "whipping cream",
    "sour cream", "cream cheese", "greek yogurt", "goat cheese", "cottage cheese", "egg yolks", "egg whites", "ice cream", "puff pastry", "frozen peas",
    "frozen spinach", "all-purpose flour", "bread flour", "brown sugar", "powdered sugar", "icing sugar", "ramen noodles", "olive oil", "vegetable oil",
    "canola oil", "sesame oil", "soy sauce", "maple syrup", "date syrup", "tomato paste", "canned tomatoes", "crushed tomatoes", "tomato sauce",
    "peanut butter", "chocolate chips", "baking powder", "baking soda", "pine nuts", "sesame seeds", "hot sauce", "corn starch", "coconut milk",
    "coconut cream", "canned tuna", "fish sauce", "oyster sauce", "vanilla extract", "kosher salt", "sea salt", "black pepper", "pepper flakes",
    "red pepper flakes", "chili flakes", "smoked paprika", "sweet paprika", "dried oregano", "chili powder", "curry powder", "garam masala", "bay leaf",
    "bay leaves", "ground coriander", "coriander seeds", "ground ginger", "garlic powder", "onion powder", "dried thyme", "fennel seeds", "mustard seeds",
    "everything bagel seasoning", "ras el hanout", "salt and pepper", "chicken stock", "vegetable stock", "chicken broth", "vegetable broth", "beef stock", "beef broth", "fish stock", "five spice", "star anise", "white wine", "red wine", "orange juice", "sparkling water", "club soda",
    "aluminum foil", "parchment paper", "baking paper", "paper towels", "plastic wrap", "zip bags", "english muffins", "lemon grass",
    "עגבניות שרי", "תפוח אדמה", "תפוחי אדמה", "שעועית ירוקה", "בצל ירוק", "עשבי תיבול", "פירות יער", "חזה עוף", "בשר טחון", "שמנת מתוקה", "שמנת חמוצה",
    "גבינת שמנת", "גבינת עיזים", "בצק עלים", "בצק פילו", "קמח לבן", "סוכר חום", "אבקת סוכר", "שמן זית", "שמן קנולה", "שמן שומשום", "רוטב סויה",
    "סירופ מייפל", "רסק עגבניות", "עגבניות מרוסקות", "גרגרי חומוס", "אבקת מרק", "חמאת בוטנים", "שוקולד ציפס", "אבקת אפייה", "סודה לשתייה",
    "שיבולת שועל", "פירורי לחם", "אגוזי מלך", "חלב קוקוס", "קרם קוקוס", "ירקות כבושים", "מלח גס", "פלפל שחור", "פפריקה מעושנת", "פפריקה מתוקה",
    "אגוז מוסקט", "פלפל אנגלי", "צילי גרוס", "פלפל חריף גרוס", "עלי דפנה", "כוסברה טחונה", "שום גבישי", "אבקת שום", "אבקת בצל", "ראס אל חנות",
    "יין לבן", "יין אדום", "מיץ תפוזים", "מים מוגזים", "נייר אפייה", "נייר כסף", "מגבות נייר", "ניילון נצמד",
  ].map(norm);
  KNOWN.forEach((p) => REAL.add(p));
  // words that only describe ("white", "fresh", "ground") never decide an aisle on their own
  const STOP = new Set(("white red green fresh ground baby dried sweet smoked sea black brown powdered icing all-purpose kosher canned crushed hot " +
    "heavy whipping sour greek goat cottage extract paper bags zip plastic aluminum club sparkling five star ras el hanout english spring bay grass " +
    "seeds powder flakes leaf leaves pepper everything vegetable bread-flour lemon-grass minced chicken-breast בצק אבקת שמן גבינת עלי מלח-גס").split(" "));
  const TABLE = PHRASES.filter(([p]) => (!p.includes(" ") && !STOP.has(p)) || REAL.has(p)).sort((a, b) => b[0].length - a[0].length);
  // Hebrew words take a prefix (ה, ו, ב, ל, מ, ש, כ); English ones may end in s
  const HEB = /[֐-׿]/;
  function of(item) {
    const s = " " + norm(item) + " ";
    for (const [p, aisle] of TABLE) {
      if (HEB.test(p) ? new RegExp(`[ ][והבלמשכ]{0,2}${p}(?=[ ])`).test(s) : s.includes(" " + p + " ") || s.includes(" " + p + "s ") || s.includes(" " + p + "es ")) return aisle;
    }
    return "other";
  }
  window.MatkonAisles = { of, ORDER, NAMES };
})();
