import React, { useState, useEffect } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Database, MessageSquare, BarChart, Code, Cpu } from "lucide-react";

const API_BASE_URL = "http://localhost:5000/api/v1";

export default function WooshHomePage() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [messageIdCounter, setMessageIdCounter] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [dbStatus, setDbStatus] = useState(null);

  useEffect(() => {
    // Check database health on component mount
    checkDatabaseHealth();
  }, []);

  const checkDatabaseHealth = async () => {
    try {
      const response = await fetch("http://localhost:5000/health");
      const data = await response.json();
      setDbStatus(data.status === "healthy");
    } catch (error) {
      setDbStatus(false);
      console.error("Health check failed:", error);
    }
  };

  const addMessage = (text, sender, sqlQuery, queryResult, error) => {
    const newMessage = {
      id: messageIdCounter,
      text,
      sender,
      sqlQuery,
      queryResult,
      error,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, newMessage]);
    setMessageIdCounter((prev) => prev + 1);
    setInputValue("");
  };

  const removeMessage = (id) => {
    setMessages((prev) => prev.filter((message) => message.id !== id));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    setIsLoading(true);
    addMessage(inputValue, "user");

    try {
      const response = await fetch(`${API_BASE_URL}/convert`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: inputValue,
          execute: true, // Set to true to get query results
        }),
      });

      const data = await response.json();

      if (data.status === "success" || data.status === "warning") {
        addMessage(
          data.status === "warning" 
            ? `Warning: ${data.warnings}\nSuggested Fix Applied` 
            : "Query processed successfully",
          "system",
          data.sql_query,
          data.results || "Query executed successfully",
        );
      } else {
        addMessage(
          "Error processing query",
          "system",
          null,
          null,
          data.error || "Unknown error occurred"
        );
      }
    } catch (error) {
      addMessage(
        "Failed to connect to the server",
        "system",
        null,
        null,
        error.message
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-indigo-100 to-white">
      <header className="bg-white shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <div className="flex items-center">
            <Database className="h-8 w-8 text-indigo-500 mr-2" />
            <h1 className="text-2xl font-bold text-gray-900">Woosh</h1>
          </div>
          <div className="flex items-center gap-4">
            <div className={`flex items-center ${dbStatus ? 'text-green-500' : 'text-red-500'}`}>
              <div className={`w-2 h-2 rounded-full ${dbStatus ? 'bg-green-500' : 'bg-red-500'} mr-2`}></div>
              {dbStatus ? 'Connected' : 'Disconnected'}
            </div>
            <nav>
              <ul className="flex space-x-4">
                <li>
                  <Button variant="ghost">Home</Button>
                </li>
                <li>
                  <Button variant="ghost">Documentation</Button>
                </li>
              </ul>
            </nav>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <Card className="w-full">
          <CardHeader>
            <CardTitle>Welcome to Woosh</CardTitle>
            <CardDescription>
              Translate natural language to SQL queries with ease
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="chat" className="w-full">
              <TabsList className="grid w-full grid-cols-2 mb-4">
                <TabsTrigger value="chat">Chat</TabsTrigger>
                <TabsTrigger value="history">Query History</TabsTrigger>
              </TabsList>
              <TabsContent value="chat">
                <ScrollArea className="h-[400px] w-full pr-4 mb-4 border rounded-lg p-4">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`mb-4 p-3 rounded-lg ${
                        message.sender === "user"
                          ? "bg-indigo-100 ml-auto"
                          : "bg-gray-100"
                      } max-w-[80%] ${
                        message.sender === "user" ? "text-right" : "text-left"
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <Avatar>
                          <AvatarFallback>
                            {message.sender === "user" ? "U" : "S"}
                          </AvatarFallback>
                        </Avatar>
                        <div className="flex-1">
                          <p className="font-semibold">
                            {message.sender === "user" ? "You" : "Woosher"}
                          </p>
                          <p>{message.text}</p>
                          {message.sqlQuery && (
                            <div className="mt-2 p-2 bg-gray-800 text-green-400 rounded">
                              <p className="text-xs font-mono">{message.sqlQuery}</p>
                            </div>
                          )}
                          {message.queryResult && (
                            <div className="mt-2 p-2 bg-gray-100 rounded">
                              <pre className="text-xs overflow-x-auto">
                                {typeof message.queryResult === 'string' 
                                  ? message.queryResult 
                                  : JSON.stringify(message.queryResult, null, 2)}
                              </pre>
                            </div>
                          )}
                          {message.error && (
                            <div className="mt-2 p-2 bg-red-100 text-red-600 rounded">
                              <p className="text-xs">{message.error}</p>
                            </div>
                          )}
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeMessage(message.id)}
                        className="mt-1 text-xs"
                      >
                        Remove
                      </Button>
                    </div>
                  ))}
                </ScrollArea>
                <form onSubmit={handleSubmit} className="flex gap-2">
                  <Input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    placeholder="Describe your query in natural language..."
                    className="flex-grow"
                    disabled={isLoading || !dbStatus}
                  />
                  <Button type="submit" disabled={isLoading || !dbStatus}>
                    {isLoading ? "Processing..." : "Translate & Execute"}
                  </Button>
                </form>
              </TabsContent>
              <TabsContent value="history">
                <div className="h-[400px] flex items-center justify-center bg-gray-100 rounded-lg">
                  <BarChart className="h-16 w-16 text-gray-400" />
                  <p className="text-gray-500 ml-4">
                    Query history and analytics coming soon!
                  </p>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </main>

      <footer className="bg-gray-100 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex justify-between items-center">
            <p>&copy; 2024 Woosh. All rights reserved.</p>
            <div className="flex space-x-4">
              <Button variant="ghost" size="sm">
                API Documentation
              </Button>
              <Button variant="ghost" size="sm">
                Privacy Policy
              </Button>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}