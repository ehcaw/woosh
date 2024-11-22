import React, { useState } from "react";
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

export default function WooshHomePage() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [messageIdCounter, setMessageIdCounter] = useState(0);

  const addMessage = (text, sender, sqlQuery, queryResult) => {
    const newMessage = {
      id: messageIdCounter,
      text,
      sender,
      sqlQuery,
      queryResult,
    };
    setMessages([...messages, newMessage]);
    setMessageIdCounter(messageIdCounter + 1);
    setInputValue("");
  };

  const removeMessage = (id) => {
    setMessages(messages.filter((message) => message.id !== id));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (inputValue.trim()) {
      addMessage(inputValue, "user");
      // Simulate SQL translation and query execution (replace with actual implementation)
      setTimeout(() => {
        const simulatedSqlQuery = `SELECT * FROM users WHERE name LIKE '%${inputValue}%'`;
        const simulatedQueryResult =
          "Query executed successfully. 5 rows returned.";
        addMessage(
          "I've translated your request to SQL and executed the query.",
          "system",
          simulatedSqlQuery,
          simulatedQueryResult,
        );
      }, 1000);
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
          <nav>
            <ul className="flex space-x-4">
              <li>
                <Button variant="ghost">Home</Button>
              </li>
              <li>
                <Button variant="ghost">Documentation</Button>
              </li>
              <li>
                <Button variant="ghost">Pricing</Button>
              </li>
            </ul>
          </nav>
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
                          <AvatarImage
                            src={
                              message.sender === "user"
                                ? "/user-avatar.png"
                                : "/system-avatar.png"
                            }
                          />
                          <AvatarFallback>
                            {message.sender === "user" ? "U" : "S"}
                          </AvatarFallback>
                        </Avatar>
                        <div>
                          <p className="font-semibold">
                            {message.sender === "user" ? "You" : "Woosher"}
                          </p>
                          <p>{message.text}</p>
                          {message.sqlQuery && (
                            <div className="mt-2 p-2 bg-gray-800 text-green-400 rounded">
                              <p className="text-xs font-mono">
                                {message.sqlQuery}
                              </p>
                            </div>
                          )}
                          {message.queryResult && (
                            <div className="mt-2 p-2 bg-gray-100 rounded">
                              <p className="text-xs">{message.queryResult}</p>
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
                  />
                  <Button type="submit">Translate & Execute</Button>
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

        <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Natural Language to SQL</CardTitle>
              <CardDescription>Effortless query translation</CardDescription>
            </CardHeader>
            <CardContent>
              <MessageSquare className="h-12 w-12 text-indigo-500 mb-4" />
              <p>
                Transform your natural language requests into precise SQL
                queries with our advanced AI technology.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Intelligent Query Execution</CardTitle>
              <CardDescription>Powered by AI agents</CardDescription>
            </CardHeader>
            <CardContent>
              <Cpu className="h-12 w-12 text-green-500 mb-4" />
              <p>
                Our AI agents execute your queries efficiently, optimizing for
                performance and accuracy.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Advanced Data Operations</CardTitle>
              <CardDescription>Beyond simple queries</CardDescription>
            </CardHeader>
            <CardContent>
              <Code className="h-12 w-12 text-purple-500 mb-4" />
              <p>
                Perform complex data operations and transformations on your
                query results with ease.
              </p>
            </CardContent>
          </Card>
        </div>
      </main>

      <footer className="bg-gray-100 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex justify-between items-center">
            <p>&copy; 2023 SQLWhisperer. All rights reserved.</p>
            <div className="flex space-x-4">
              <Button variant="ghost" size="sm">
                API Documentation
              </Button>
              <Button variant="ghost" size="sm">
                Privacy Policy
              </Button>
              <Button variant="ghost" size="sm">
                Terms of Service
              </Button>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
